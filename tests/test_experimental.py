from types import SimpleNamespace

import pandas as pd
import pytest

from swingbot.experimental import generate_trend_pullback, select_signals


def fixture():
    row = dict(Open=104, Close=105, High=106, Low=103, EMA20=103, SMA50=100, SMA200=90,
               ATR14=2, EMA20Slope5=0.01, RelativeStrength20=0.02,
               AverageDollarVolume20=20_000_000, RVOL=1.2)
    frame = pd.DataFrame([row.copy() for _ in range(8)], index=pd.bdate_range("2025-01-01", periods=8))
    frame.iloc[-2, frame.columns.get_loc("High")] = 104
    frame.iloc[-2, frame.columns.get_loc("RVOL")] = 0.8
    settings = SimpleNamespace(minimum_history=6, require_benchmark_uptrend=True,
        minimum_price=5, minimum_average_dollar_volume=10_000_000, maximum_extension_atr=2,
        pullback_distance_atr=0.5, target_r_multiple=2, minimum_reward_risk=1.5)
    return frame, settings


def test_valid_setup_has_structural_stop_and_target():
    frame, settings = fixture()
    signal = generate_trend_pullback("TEST", frame, settings)[0]
    assert signal["stop"] < signal["entry"] < signal["target"]
    assert signal["reward_risk"] == 2


@pytest.mark.parametrize("column,value", [("SMA200", 110), ("RelativeStrength20", -0.01),
    ("RVOL", 0.5), ("Open", 106), ("ATR14", 0), ("EMA20", float("nan"))])
def test_invalid_confirmation_or_trend_is_rejected(column, value):
    frame, settings = fixture()
    frame.iloc[-1, frame.columns.get_loc(column)] = value
    assert generate_trend_pullback("TEST", frame, settings) == []


def test_market_filter_rejects_downtrend():
    frame, settings = fixture()
    assert generate_trend_pullback("TEST", frame, settings, False) == []


def test_quiet_pullback_must_precede_signal():
    frame, settings = fixture()
    frame["RVOL"] = 1.2
    assert generate_trend_pullback("TEST", frame, settings) == []


def test_blend_deduplicates_and_keeps_predeclared_priority():
    baseline = [{"strategy": "breakout", "score": 95}, {"strategy": "pullback", "score": 95}]
    experimental = [{"strategy": "experimental_ema_pullback", "score": 75}]
    assert select_signals(baseline, experimental, "blend") == experimental
    assert len(select_signals(baseline, [], "baseline")) == 1
    assert select_signals(baseline, [], "blend")[0]["strategy"] == "breakout"


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        select_signals([], [], "unknown")


def test_future_rows_are_not_required_for_signal():
    frame, settings = fixture()
    before = generate_trend_pullback("TEST", frame, settings)
    extended = pd.concat([frame, frame.iloc[[-1]].set_axis([pd.Timestamp("2025-02-01")])])
    extended.iloc[-1, extended.columns.get_loc("Close")] = 9999
    assert generate_trend_pullback("TEST", extended.iloc[:-1], settings) == before
