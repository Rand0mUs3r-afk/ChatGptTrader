"""Six predeclared daily-bar hypotheses; not validated trading systems."""
import math

import pandas as pd

FAMILIES = ("rsi2_dip", "band_reversion", "compression_breakout", "failed_breakdown", "gap_recovery", "donchian55")


def add_features(frame):
    frame = frame.copy()
    close = frame["Close"]
    change = close.diff()
    gain = change.clip(lower=0).ewm(alpha=0.5, adjust=False, min_periods=2).mean()
    loss = (-change.clip(upper=0)).ewm(alpha=0.5, adjust=False, min_periods=2).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, float("nan")))
    rsi = rsi.mask((loss == 0) & (gain > 0), 100).mask((loss == 0) & (gain == 0), 50)
    frame["RSI2"] = rsi
    frame["LowerBand20"] = close.rolling(20).mean() - 2 * close.rolling(20).std(ddof=0)
    frame["High55"] = frame["High"].rolling(55).max().shift(1)
    ratio = frame["ATR14"] / close
    frame["Compression"] = ratio.shift(1) / ratio.shift(1).rolling(120).median()
    frame["PreviousClose"] = close.shift(1)
    return frame


def generate_candidates(ticker, frame, settings):
    if len(frame) < settings.minimum_history:
        return {}
    row = frame.iloc[-1]
    fields = ["Open", "High", "Low", "Close", "ATR14", "EMA20", "SMA50", "SMA200",
              "RSI2", "LowerBand20", "High55", "Compression", "PreviousClose",
              "PriorHigh20", "PriorLow20", "AverageDollarVolume20"]
    if not all(math.isfinite(float(row[field])) for field in fields):
        return {}
    close, atr = float(row["Close"]), float(row["ATR14"])
    if atr <= 0 or close < settings.minimum_price or row["AverageDollarVolume20"] < settings.minimum_average_dollar_volume:
        return {}
    bullish_long_trend = close > row["SMA200"]
    conditions = {
        "rsi2_dip": bullish_long_trend and row["RSI2"] < 10,
        "band_reversion": bullish_long_trend and close < row["LowerBand20"],
        "compression_breakout": row["Compression"] < 0.75 and close > row["PriorHigh20"],
        "failed_breakdown": row["Low"] < row["PriorLow20"] < close and close > row["Open"],
        "gap_recovery": row["Open"] < row["PreviousClose"] - 0.75 * atr and close > row["Open"] + 0.5 * atr,
        "donchian55": close > row["High55"] and row["EMA20"] > row["SMA50"],
    }
    stop = float(frame["Low"].iloc[-5:].min()) - 0.1 * atr
    if not 0 < stop < close:
        return {}
    risk = close - stop
    output = {}
    for family, passes in conditions.items():
        if passes:
            reason = (f"Hypothesis {family} passed at signal close. Close={close:.4f}; RSI2={row['RSI2']:.2f}; "
                      f"lower band={row['LowerBand20']:.4f}; prior high20={row['PriorHigh20']:.4f}; "
                      f"prior low20={row['PriorLow20']:.4f}; prior high55={row['High55']:.4f}; "
                      f"compression={row['Compression']:.4f}; open={row['Open']:.4f}; "
                      f"previous close={row['PreviousClose']:.4f}; ATR={atr:.4f}.")
            output[family] = [dict(ticker=ticker, strategy=family, signal_date=str(frame.index[-1].date()),
                entry=close, stop=stop, target=close + settings.target_r_multiple * risk,
                risk_per_share=risk, reward_risk=settings.target_r_multiple, score=70.0, reason=reason)]
    return output
