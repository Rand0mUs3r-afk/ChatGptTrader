import json

import pandas as pd
import pytest

from swingbot.journal_report import capture_trade, enrich_journal, render_journal


def sample(pnl):
    rows = []
    for i, value in enumerate(pnl):
        rows.append(dict(ticker=f"T{i}", strategy="test", entry_date="2025-01-01", exit_date="2025-01-02",
                         net_pnl=value, entry=100, exit=101, stop=95, target=110, shares=10,
                         equity_before=10000, equity_after=10000 + value, exit_reason="time_exit"))
    columns = ["ticker", "strategy", "entry_date", "exit_date", "net_pnl", "entry", "exit", "stop",
               "target", "shares", "equity_before", "equity_after", "exit_reason"]
    journal = pd.DataFrame(rows, columns=columns)
    summary = dict(starting_equity=10000, final_equity=10000 + sum(pnl), return_pct=sum(pnl) / 100,
                   max_closed_trade_drawdown_pct=0, skipped_candidates=3)
    return journal, summary


@pytest.mark.parametrize("pnl,wins,losses", [([], 0, 0), ([1, 2, -1, -2, -3, 4], 2, 3),
    ([1, 0, 1], 1, 0), ([-1, 0, -1], 0, 1), ([1, 2, 3], 3, 0), ([-1, -2], 0, 2)])
def test_streaks_and_breakeven_resets(pnl, wins, losses):
    journal, summary = sample(pnl)
    journal, summary = enrich_journal(journal, summary, pd.DataFrame())
    assert summary["max_consecutive_wins"] == wins
    assert summary["max_consecutive_losses"] == losses
    assert len(journal) == len(pnl)


def test_money_totals_and_rates_use_only_accepted_trades():
    journal, summary = sample([100, 200, -50, -100, 0])
    journal, summary = enrich_journal(journal, summary, pd.DataFrame())
    assert summary["total_money_won"] == 300
    assert summary["total_money_lost"] == 150
    assert summary["net_pnl"] == 150
    assert summary["wins"] == summary["losses"] == 2
    assert summary["win_rate_pct"] == summary["loss_rate_pct"] == 40
    assert summary["breakeven_rate_pct"] == 20
    assert summary["trades"] == 5
    json.dumps(summary, allow_nan=False)


def test_capture_preserves_signal_evidence_without_mutating_trade():
    trade = dict(ticker="TEST")
    frame = pd.DataFrame([dict(Close=105, EMA20=103, SMA50=float("nan"))])
    result = capture_trade(trade, dict(reason="Quiet pullback confirmed", score=75), frame, True, "blend")
    assert "entry_reason" not in trade
    assert result["entry_reason"] == "Quiet pullback confirmed"
    snapshot = json.loads(result["signal_snapshot"])
    assert snapshot["Close"] == 105 and snapshot["SMA50"] is None
    assert snapshot["benchmark_uptrend"] is True


def test_reasons_join_the_correct_trade():
    journal, summary = sample([10, -5])
    candidates = journal.iloc[::-1].copy()
    candidates["entry_reason"] = ["Second reason", "First reason"]
    candidates["signal_snapshot"] = "{}"
    candidates["selection_policy"] = "Fixed policy"
    result, _ = enrich_journal(journal, summary, candidates)
    assert result["entry_reason"].tolist() == ["First reason", "Second reason"]
    assert result["outcome"].tolist() == ["WIN", "LOSS"]


def test_duplicate_reason_keys_fail_loudly():
    journal, summary = sample([10])
    candidates = pd.concat([journal, journal], ignore_index=True)
    for column in ("entry_reason", "signal_snapshot", "selection_policy"):
        candidates[column] = "same"
    with pytest.raises(ValueError, match="Ambiguous"):
        enrich_journal(journal, summary, candidates)


def test_report_displays_all_requested_metrics_and_reasons():
    journal, summary = sample([10, -5])
    journal, summary = enrich_journal(journal, summary, pd.DataFrame())
    text = render_journal(journal, summary, "blend / full")
    for term in ("Total trades taken", "Total money won", "Total money lost", "Win / loss",
                 "Longest winning streak", "Longest losing streak", "Why entered", "Why selected"):
        assert term in text
    assert "Why entered" not in render_journal(journal, summary, "blend", include_trades=False)


def test_empty_report_is_explicit():
    journal, summary = sample([])
    journal, summary = enrich_journal(journal, summary, pd.DataFrame())
    assert "No trades were taken" in render_journal(journal, summary, "empty")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_invalid_pnl_rejected(value):
    journal, summary = sample([value])
    with pytest.raises(ValueError, match="finite"):
        enrich_journal(journal, summary, pd.DataFrame())
