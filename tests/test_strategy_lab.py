from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from swingbot.strategy_lab import FAMILIES, add_features, generate_candidates


def fixture():
    row = dict(Open=100, High=102, Low=99, Close=101, ATR14=2, EMA20=100,
               SMA50=98, SMA200=90, RSI2=50, LowerBand20=95, High55=110,
               Compression=1.0, PreviousClose=100, PriorHigh20=105, PriorLow20=96,
               AverageDollarVolume20=20_000_000)
    frame = pd.DataFrame([row.copy() for _ in range(230)], index=pd.bdate_range("2024-01-01", periods=230), dtype=float)
    settings = SimpleNamespace(minimum_history=220, minimum_price=5,
        minimum_average_dollar_volume=10_000_000, target_r_multiple=2)
    return frame, settings


@pytest.mark.parametrize("family,changes", [
    ("rsi2_dip", dict(RSI2=5)),
    ("band_reversion", dict(LowerBand20=103)),
    ("compression_breakout", dict(Compression=0.5, PriorHigh20=100)),
    ("failed_breakdown", dict(Low=94, PriorLow20=96)),
    ("gap_recovery", dict(Open=97)),
    ("donchian55", dict(High55=100)),
])
def test_each_family_can_generate_valid_plan(family, changes):
    frame, settings = fixture()
    for key, value in changes.items():
        frame.loc[frame.index[-1], key] = value
    signal = generate_candidates("TEST", frame, settings)[family][0]
    assert signal["stop"] < signal["entry"] < signal["target"]
    assert family in signal["reason"]


def test_neutral_fixture_has_no_setup():
    frame, settings = fixture()
    assert generate_candidates("TEST", frame, settings) == {}


@pytest.mark.parametrize("column,value", [("ATR14", 0), ("Close", 1),
    ("AverageDollarVolume20", 1), ("RSI2", float("nan"))])
def test_invalid_or_untradable_inputs_rejected(column, value):
    frame, settings = fixture()
    frame.loc[frame.index[-1], column] = value
    assert generate_candidates("TEST", frame, settings) == {}


def test_features_are_prefix_invariant():
    dates = pd.bdate_range("2020-01-01", periods=300)
    close = np.linspace(50, 100, 300)
    bars = pd.DataFrame(dict(Close=close, High=close+1, ATR14=2), index=dates)
    short = add_features(bars.iloc[:250])
    long = add_features(bars)
    pd.testing.assert_frame_equal(short, long.iloc[:250])
    assert long["High55"].iloc[-1] == bars["High"].iloc[-56:-1].max()


def test_rsi2_stays_in_range():
    bars = pd.DataFrame(dict(Close=np.arange(1, 301), High=np.arange(2, 302), ATR14=1))
    assert add_features(bars)["RSI2"].dropna().between(0, 100).all()
    assert len(FAMILIES) == 6
