
from __future__ import annotations

import pandas as pd

from swingbot.config import DEFAULT_SETTINGS, Settings


def _score(
    trend_ok: bool,
    relative_strength: float,
    rvol: float,
    extension_atr: float,
    setup_ok: bool,
    benchmark_ok: bool,
) -> float:
    """Transparent heuristic score, not a probability of profit."""
    score = 0.0

    if trend_ok:
        score += 20

    if relative_strength > 0:
        score += 10
    if relative_strength > 0.02:
        score += 10

    if rvol >= 1.5:
        score += 10
    if rvol >= 2.0:
        score += 5

    if 0 <= extension_atr <= 1.0:
        score += 10
    elif 1.0 < extension_atr <= 2.0:
        score += 5

    if setup_ok:
        score += 20

    if benchmark_ok:
        score += 10

    return min(score, 100.0)


def generate_signals(
    ticker: str,
    features: pd.DataFrame,
    settings: Settings = DEFAULT_SETTINGS,
    benchmark_uptrend: bool = True,
) -> list[dict]:
    """Evaluate the latest completed bar for supported strategies."""
    if len(features) < settings.minimum_history:
        return []

    row = features.iloc[-1]
    previous = features.iloc[-2]

    required = [
        "Close",
        "High",
        "Low",
        "EMA20",
        "SMA50",
        "ATR14",
        "RVOL",
        "AverageDollarVolume20",
        "PriorHigh20",
        "PriorLow20",
        "ExtensionATR",
        "RelativeStrength20",
        "EMA20Slope5",
    ]

    if row[required].isna().any():
        return []

    close = float(row["Close"])
    high = float(row["High"])
    low = float(row["Low"])
    ema20 = float(row["EMA20"])
    sma50 = float(row["SMA50"])
    atr = float(row["ATR14"])
    rvol = float(row["RVOL"])
    dollar_volume = float(row["AverageDollarVolume20"])
    prior_high = float(row["PriorHigh20"])
    prior_low = float(row["PriorLow20"])
    extension = float(row["ExtensionATR"])
    relative_strength = float(row["RelativeStrength20"])
    ema_slope = float(row["EMA20Slope5"])

    if close < settings.minimum_price:
        return []

    if dollar_volume < settings.minimum_average_dollar_volume:
        return []

    trend_ok = (
        close > ema20
        and ema20 > sma50
        and ema_slope > 0
    )

    benchmark_ok = (
        benchmark_uptrend
        if settings.require_benchmark_uptrend
        else True
    )

    if not trend_ok or not benchmark_ok:
        return []

    if rvol < settings.minimum_relative_volume:
        return []

    if relative_strength <= 0:
        return []

    if extension < 0 or extension > settings.maximum_extension_atr:
        return []

    # A structural stop below the recent swing low, with an ATR buffer.
    recent_swing_low = float(features["Low"].iloc[-5:].min())
    stop = recent_swing_low - 0.1 * atr

    if stop >= close:
        return []

    risk_per_share = close - stop
    if risk_per_share <= 0:
        return []

    target = close + settings.target_r_multiple * risk_per_share
    reward_risk = (target - close) / risk_per_share

    if reward_risk < settings.minimum_reward_risk:
        return []

    candidates: list[dict] = []

    # Strategy A: breakout above the previous 20-session high.
    breakout = close > prior_high

    if breakout:
        score = _score(
            trend_ok,
            relative_strength,
            rvol,
            extension,
            setup_ok=True,
            benchmark_ok=benchmark_ok,
        )

        if score >= settings.minimum_signal_score:
            candidates.append({
                "ticker": ticker,
                "strategy": "breakout",
                "signal_date": str(features.index[-1].date()),
                "entry": close,
                "stop": stop,
                "target": target,
                "risk_per_share": risk_per_share,
                "reward_risk": reward_risk,
                "score": score,
                "close": close,
                "rvol": rvol,
                "relative_strength": relative_strength,
                "extension_atr": extension,
                "reason": "Close above prior 20-session high",
            })

    # Strategy B: pullback near the EMA, followed by a bullish close
    # above the previous session's high.
    pullback_near_ema = (
        abs(low - ema20)
        <= settings.pullback_distance_atr * atr
    )

    bullish_confirmation = (
        close > float(previous["High"])
        and close > float(previous["Open"])
    )

    pullback = pullback_near_ema and bullish_confirmation

    if pullback:
        score = _score(
            trend_ok,
            relative_strength,
            rvol,
            extension,
            setup_ok=True,
            benchmark_ok=benchmark_ok,
        )

        if score >= settings.minimum_signal_score:
            candidates.append({
                "ticker": ticker,
                "strategy": "pullback",
                "signal_date": str(features.index[-1].date()),
                "entry": close,
                "stop": stop,
                "target": target,
                "risk_per_share": risk_per_share,
                "reward_risk": reward_risk,
                "score": score,
                "close": close,
                "rvol": rvol,
                "relative_strength": relative_strength,
                "extension_atr": extension,
                "reason": "EMA pullback with bullish confirmation",
            })

    return candidates
