
from __future__ import annotations

import numpy as np
import pandas as pd

from swingbot.config import DEFAULT_SETTINGS, Settings


def calculate_rsi(
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Wilder-style RSI using exponentially smoothed gains and losses."""
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False,
    ).mean()

    average_loss = losses.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False,
    ).mean()

    relative_strength = average_gain / average_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relative_strength))

    # A positive series with no losses has RSI 100.
    rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100)
    # A flat series with no gains or losses is assigned RSI 50.
    rsi = rsi.mask((average_loss == 0) & (average_gain == 0), 50)

    return rsi


def calculate_features(
    bars: pd.DataFrame,
    benchmark_close: pd.Series | None = None,
    settings: Settings = DEFAULT_SETTINGS,
) -> pd.DataFrame:
    """Calculate features using only current and historical observations."""
    frame = bars.copy()

    close = frame["Close"]
    high = frame["High"]
    low = frame["Low"]
    volume = frame["Volume"]

    frame["EMA20"] = close.ewm(
        span=settings.ema_period,
        adjust=False,
        min_periods=settings.ema_period,
    ).mean()

    frame["SMA50"] = close.rolling(
        settings.sma_period
    ).mean()

    frame["SMA200"] = close.rolling(
        settings.long_sma_period
    ).mean()

    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    frame["ATR14"] = true_range.ewm(
        alpha=1 / settings.atr_period,
        min_periods=settings.atr_period,
        adjust=False,
    ).mean()

    frame["RSI14"] = calculate_rsi(
        close, settings.rsi_period
    )

    frame["AverageVolume20"] = volume.rolling(
        settings.volume_period
    ).mean().shift(1)

    frame["RVOL"] = (
        volume / frame["AverageVolume20"].replace(0, np.nan)
    )

    frame["AverageDollarVolume20"] = (
        (close * volume).rolling(20).mean().shift(1)
    )

    frame["PriorHigh20"] = high.rolling(
        settings.breakout_period
    ).max().shift(1)

    frame["PriorLow20"] = low.rolling(
        settings.breakout_period
    ).min().shift(1)

    frame["ExtensionATR"] = (
        (close - frame["EMA20"])
        / frame["ATR14"].replace(0, np.nan)
    )

    period = settings.relative_strength_period
    stock_return = close.pct_change(period)

    if benchmark_close is not None:
        aligned_benchmark = benchmark_close.reindex(
            frame.index
        ).ffill()

        benchmark_return = aligned_benchmark.pct_change(period)

        frame["RelativeStrength20"] = (
            stock_return - benchmark_return
        )
    else:
        frame["RelativeStrength20"] = np.nan

    frame["EMA20Slope5"] = (
        frame["EMA20"] / frame["EMA20"].shift(5) - 1
    )

    frame["DollarVolume"] = close * volume

    return frame
