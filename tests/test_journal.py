from types import SimpleNamespace

import pandas as pd
import pytest

from swingbot.journal import build_journal, format_journal


def settings(**overrides):
    values = dict(account_equity=10000.0, risk_fraction=0.01,
                  maximum_position_fraction=0.2, slippage_bps=0, commission_per_share=0)
    values.update(overrides)
    return SimpleNamespace(**values)


def trade(start="2025-01-01", end="2025-01-02", pnl=2.0, ticker="AAA"):
    return dict(ticker=ticker, strategy="breakout", entry_date=start, exit_date=end,
                entry=100.0, exit=100.0 + pnl, stop=95.0, target=110.0,
                exit_reason="time_exit", net_pnl_per_share=pnl, net_r_multiple=pnl / 5)


def test_empty_journal_keeps_starting_equity():
    journal, summary = build_journal(pd.DataFrame(), settings())
    assert journal.empty
    assert summary["starting_equity"] == summary["final_equity"] == 10000
    assert summary["return_pct"] == summary["max_closed_trade_drawdown_pct"] == 0


def test_sized_pnl_and_final_equity():
    journal, summary = build_journal(pd.DataFrame([trade()]), settings())
    assert journal.iloc[0]["shares"] == 20
    assert summary["final_equity"] == 10040
    assert summary["net_pnl"] == 40
    assert summary["return_pct"] == pytest.approx(0.4)


def test_overlap_and_exit_day_reentry_are_skipped():
    candidates = [trade(), trade(ticker="BBB"), trade("2025-01-02", "2025-01-03", ticker="CCC")]
    journal, summary = build_journal(pd.DataFrame(candidates), settings())
    assert len(journal) == 1
    assert summary["skipped_candidates"] == 2


def test_ties_do_not_select_future_winner():
    candidates = [trade(pnl=10, ticker="ZZZ"), trade(pnl=-5, ticker="AAA")]
    journal, summary = build_journal(pd.DataFrame(candidates), settings())
    assert journal.iloc[0]["ticker"] == "AAA"
    assert summary["final_equity"] == 9900
    assert summary["max_closed_trade_drawdown_pct"] == pytest.approx(1)


def test_equity_reconciles_and_summary_renders():
    candidates = [trade(), trade("2025-01-03", "2025-01-06", pnl=-5)]
    journal, summary = build_journal(pd.DataFrame(candidates), settings())
    assert summary["final_equity"] == summary["starting_equity"] + journal["net_pnl"].sum()
    text = format_journal(summary)
    assert "Starting equity" in text and "Final equity" in text
    assert "closed trades only" in text


def test_costs_reduce_position_size():
    journal, _ = build_journal(pd.DataFrame([trade()]), settings(slippage_bps=10))
    assert journal.iloc[0]["shares"] == 19


@pytest.mark.parametrize("equity", [0, -1, float("nan"), float("inf")])
def test_invalid_equity_rejected(equity):
    with pytest.raises(ValueError):
        build_journal(pd.DataFrame(), settings(account_equity=equity))


def test_invalid_dates_rejected():
    with pytest.raises(ValueError):
        build_journal(pd.DataFrame([trade("2025-01-03", "2025-01-01")]), settings())
