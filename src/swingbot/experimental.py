"""Experimental trend pullback; fixed hypotheses, not optimized parameters."""
import math


def generate_trend_pullback(ticker, features, settings, benchmark_uptrend=True):
    if len(features) < max(settings.minimum_history, 6):
        return []
    if settings.require_benchmark_uptrend and not benchmark_uptrend:
        return []
    row, previous = features.iloc[-1], features.iloc[-2]
    recent = features.iloc[-4:-1]
    fields = ["Open", "Close", "High", "Low", "EMA20", "SMA50", "SMA200", "ATR14",
              "EMA20Slope5", "RelativeStrength20", "AverageDollarVolume20", "RVOL"]
    if not all(math.isfinite(float(v)) for v in row[fields]):
        return []
    if not all(math.isfinite(float(v)) for v in recent[["Low", "EMA20", "ATR14", "RVOL"]].to_numpy().flat):
        return []
    close, atr = float(row["Close"]), float(row["ATR14"])
    if atr <= 0 or close < settings.minimum_price:
        return []
    if row["AverageDollarVolume20"] < settings.minimum_average_dollar_volume:
        return []
    if not (close > row["EMA20"] > row["SMA50"] > row["SMA200"]
            and row["EMA20Slope5"] > 0 and row["RelativeStrength20"] > 0):
        return []
    extension = (close - row["EMA20"]) / atr
    if not 0 <= extension <= settings.maximum_extension_atr:
        return []
    touches = (recent["Low"] - recent["EMA20"]).abs() <= settings.pullback_distance_atr * recent["ATR14"]
    if not (touches & (recent["RVOL"] < 1)).any():
        return []
    if not (close > previous["High"] and close > row["Open"] and row["RVOL"] >= 1):
        return []
    stop = float(features["Low"].iloc[-5:].min()) - 0.1 * atr
    risk = close - stop
    if stop <= 0 or risk <= 0 or settings.target_r_multiple < settings.minimum_reward_risk:
        return []
    return [dict(ticker=ticker, strategy="experimental_ema_pullback",
                 signal_date=str(features.index[-1].date()), entry=close, stop=stop,
                 target=close + settings.target_r_multiple * risk, risk_per_share=risk,
                 reward_risk=settings.target_r_multiple, score=75.0,
                 reason="Prior quiet 20-EMA touch and bullish recovery in aligned 20/50/200 trend")]


def select_signals(baseline, experimental, mode):
    """Deduplicate one ticker/date. Blend gives experimental signals fixed priority."""
    if mode not in ("baseline", "experimental", "blend"):
        raise ValueError("Unknown strategy mode")
    candidates = baseline if mode == "baseline" else experimental
    if mode == "blend":
        candidates = experimental or baseline
    return sorted(candidates, key=lambda signal: (-signal.get("score", 0), signal["strategy"]))[:1]
