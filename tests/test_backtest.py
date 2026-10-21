import json
from dataclasses import replace

import pandas as pd
import pytest

from swingbot.backtest import simulate_trade, summarize_trades
from swingbot.config import DEFAULT_SETTINGS


def trades(pnl, r=None):
    return pd.DataFrame({"net_pnl_per_share": pnl, "net_r_multiple": pnl if r is None else r})


@pytest.mark.parametrize("pnl,status,pf", [
    ([], "no_trades", 0.0),
    ([2.0, 1.0], "no_losing_trades", None),
    ([2.0, 0.0], "no_losing_trades", None),
    ([0.0, 0.0], "all_breakeven", 0.0),
    ([-2.0, -1.0], "finite", 0.0),
    ([4.0, -2.0], "finite", 2.0),
])
def test_summary_is_strict_json_safe(pnl, status, pf):
    result = summarize_trades(trades(pnl))
    assert result["profit_factor_status"] == status
    assert result["profit_factor"] == pf
    assert result["profit_factor_basis"] == "one_share_per_trade_not_portfolio"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), "bad"])
@pytest.mark.parametrize("column", ["net_pnl_per_share", "net_r_multiple"])
def test_invalid_observations_are_rejected(value, column):
    frame = trades([1.0])
    frame[column] = [value]
    with pytest.raises(ValueError, match="finite numeric"):
        summarize_trades(frame)


def test_missing_columns_are_rejected():
    with pytest.raises(ValueError, match="Missing trade columns"):
        summarize_trades(pd.DataFrame({"other": [1]}))


def test_summary_counts_breakeven_as_nonwinner():
    result = summarize_trades(trades([4.0, -2.0, 0.0], [2.0, -1.0, 0.0]))
    assert result["trades"] == 3
    assert result["win_rate"] == pytest.approx(1 / 3)
    assert result["average_r"] == pytest.approx(1 / 3)


def bars(rows):
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"],
                        index=pd.date_range("2025-01-01", periods=len(rows), freq="B"))


def simulate(rows, **overrides):
    settings = replace(DEFAULT_SETTINGS, slippage_bps=0.0, commission_per_share=0.0,
                       **overrides)
    return simulate_trade(bars(rows), 0,
                          {"ticker": "TEST", "strategy": "breakout", "stop": 95.0},
                          settings)


def test_entry_uses_next_open_not_signal_close():
    result = simulate([(100, 101, 99, 100), (105, 106, 104, 105)])
    assert result["entry"] == 105
    assert result["target"] == 125


def test_stop_wins_when_daily_bar_also_touches_target():
    result = simulate([(100, 101, 99, 100), (100, 111, 94, 105)])
    assert result["exit_reason"] == "stop"
    assert result["exit"] == 95


def test_gap_through_stop_exits_at_open():
    result = simulate([(100, 101, 99, 100), (100, 104, 99, 102), (90, 93, 89, 92)])
    assert result["exit_reason"] == "gap_stop"
    assert result["exit"] == 90


def test_target_gap_uses_conservative_target_fill():
    result = simulate([(100, 101, 99, 100), (100, 104, 99, 102), (115, 116, 114, 115)])
    assert result["exit_reason"] == "target_gap"
    assert result["exit"] == 110


def test_entry_below_stop_is_skipped():
    assert simulate([(100, 101, 99, 100), (94, 96, 93, 95)]) is None


def test_no_next_session_produces_no_trade():
    assert simulate([(100, 101, 99, 100)]) is None


def test_time_exit_respects_holding_sessions():
    result = simulate([(100, 101, 99, 100), (100, 104, 99, 102),
                       (102, 104, 100, 103), (103, 105, 101, 104)],
                      maximum_holding_days=2)
    assert result["exit_reason"] == "time_exit"
    assert result["exit"] == 103


def test_costs_reduce_pnl():
    frame = bars([(100, 101, 99, 100), (100, 104, 99, 102)])
    settings = replace(DEFAULT_SETTINGS, slippage_bps=10.0, commission_per_share=0.01)
    result = simulate_trade(frame, 0,
                            {"ticker": "TEST", "strategy": "breakout", "stop": 95},
                            settings)
    assert result["net_pnl_per_share"] == pytest.approx(1.778)
