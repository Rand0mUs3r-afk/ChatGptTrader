
import numpy as np
import pandas as pd

from swingbot.indicators import calculate_features, calculate_rsi


def make_bars(rows=260):
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    close = pd.Series(
        np.linspace(50, 100, rows),
        index=index,
        dtype=float,
    )

    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=index,
    )


def test_rsi_stays_within_valid_range():
    bars = make_bars()
    rsi = calculate_rsi(bars["Close"])

    valid = rsi.dropna()
    assert not valid.empty
    assert valid.between(0, 100).all()


def test_feature_engine_produces_expected_columns():
    bars = make_bars()
    features = calculate_features(bars)

    expected = {
        "EMA20",
        "SMA50",
        "SMA200",
        "ATR14",
        "RSI14",
        "RVOL",
        "PriorHigh20",
        "PriorLow20",
        "ExtensionATR",
    }

    assert expected.issubset(features.columns)


def test_prior_high_excludes_current_bar():
    bars = make_bars()
    bars.iloc[-1, bars.columns.get_loc("High")] = 500.0

    features = calculate_features(bars)

    # The artificial current-day high must not enter the prior high.
    expected = bars["High"].iloc[-21:-1].max()
    assert features["PriorHigh20"].iloc[-1] == expected


def test_average_volume_excludes_current_bar():
    bars = make_bars()
    bars.iloc[-1, bars.columns.get_loc("Volume")] = 99_000_000

    features = calculate_features(bars)

    expected = bars["Volume"].iloc[-21:-1].mean()
    assert features["AverageVolume20"].iloc[-1] == expected
