from types import SimpleNamespace

import pandas as pd
import pytest

from swingbot.short_history import MODES, choose_signal, run_trial


def bars():
    rows = [(10,11,9,10), (10,11,9,10), (10,11,9,10), (10,12.5,9.5,12)]
    rows += [(12,12.5,11.5,12)] * 11
    return pd.DataFrame(rows, columns=["Open","High","Low","Close"],
        index=pd.bdate_range("2025-01-01", periods=15), dtype=float).assign(Volume=1000000)


def settings(**updates):
    values = dict(account_equity=25000, risk_fraction=0.005, maximum_position_fraction=0.2,
                  slippage_bps=0.0, commission_per_share=0.0)
    values.update(updates)
    return SimpleNamespace(**values)


def test_signal_uses_four_bars_not_old_indicators():
    frame = bars()
    assert choose_signal(frame.iloc[:3], "breakout3") is None
    assert choose_signal(frame.iloc[:4], "breakout3") is not None


def test_prefix_signal_is_unchanged_by_future_prices():
    frame = bars()
    original = choose_signal(frame.iloc[:4], "union")
    frame.iloc[8, frame.columns.get_loc("Close")] = 999
    assert choose_signal(frame.iloc[:4], "union") == original


def test_entry_is_next_open_and_time_exit_is_explicit():
    closed, opened, daily, summary = run_trial({"TEST":bars()}, "breakout3", 1, settings())
    assert len(closed) == 1 and opened.empty
    assert closed.iloc[0]["entry_date"] == str(bars().index[4].date())
    assert closed.iloc[0]["entry"] == 12
    assert closed.iloc[0]["exit_reason"] == "time_exit"
    assert summary["final_equity"] == pytest.approx(25000)


def test_costs_reduce_flat_trade_pnl():
    frame = bars()
    low = run_trial({"TEST":frame}, "breakout3", 1, settings(slippage_bps=5))[3]
    high = run_trial({"TEST":frame}, "breakout3", 1, settings(slippage_bps=15))[3]
    assert high["realized_pnl"] < low["realized_pnl"] < 0


def test_stop_first_when_target_and_stop_both_touch():
    frame = bars()
    frame.iloc[4, frame.columns.get_loc("High")] = 30
    frame.iloc[4, frame.columns.get_loc("Low")] = 1
    closed = run_trial({"TEST":frame}, "breakout3", 3, settings())[0]
    assert closed.iloc[0]["exit_reason"] == "stop"


def test_open_trade_is_not_fabricated_as_closed():
    frame = bars()
    for i in range(13):
        frame.iloc[i] = [10,11,9,10,1000000]
    frame.iloc[13] = [10,12.5,9.5,12,1000000]
    closed, opened, daily, summary = run_trial({"TEST":frame}, "breakout3", 3, settings())
    assert closed.empty and len(opened) == 1
    assert summary["win_rate_pct"] is None
    assert summary["final_equity"] - 25000 == pytest.approx(summary["realized_pnl"] + summary["unrealized_pnl"])


def test_alphabetical_selection_and_no_parallel_positions():
    closed, opened, _, summary = run_trial({"ZZZ":bars(),"AAA":bars()}, "breakout3", 1, settings())
    assert closed["ticker"].tolist() == ["AAA"]
    assert summary["skipped_candidates"] == 1


def test_consensus_needs_two_rules():
    frame = bars().iloc[:4].copy()
    assert choose_signal(frame, "consensus") is not None
    frame.iloc[-1, frame.columns.get_loc("Open")] = 12.2
    assert choose_signal(frame, "consensus") is None


@pytest.mark.parametrize("mode", MODES)
def test_every_mode_reconciles_equity(mode):
    _, _, _, summary = run_trial({"TEST":bars()}, mode, 2, settings(slippage_bps=5))
    assert summary["final_equity"] - 25000 == pytest.approx(summary["realized_pnl"] + summary["unrealized_pnl"])


def test_invalid_or_mismatched_data_rejected():
    frame = bars()
    bad = frame.copy(); bad.iloc[0, bad.columns.get_loc("High")] = 1
    with pytest.raises(ValueError): run_trial({"TEST":bad}, "union", 1, settings())
    with pytest.raises(ValueError): run_trial({"A":frame,"B":frame.iloc[:-1]}, "union", 1, settings())


@pytest.mark.parametrize("mode", ["reversal2", "dip_rebound3", "inside_breakout"])
def test_other_base_hypotheses_can_trigger(mode):
    frame = bars().iloc[:4].copy()
    if mode == "reversal2":
        frame.iloc[2] = [10,11,9,9,1000000]
    elif mode == "dip_rebound3":
        frame.iloc[3] = [8.1,9,8,8.5,1000000]
    else:
        frame.iloc[1] = [10,13,8,11,1000000]
        frame.iloc[2] = [10,12,9,10,1000000]
        frame.iloc[3] = [10,12.5,9.5,12.2,1000000]
    assert choose_signal(frame, mode) is not None
