
from __future__ import annotations

import pandas as pd

from swingbot.config import DEFAULT_SETTINGS, Settings
from swingbot.indicators import calculate_features
from swingbot.strategies import generate_signals


def simulate_trade(
    bars: pd.DataFrame,
    signal_index: int,
    signal: dict,
    settings: Settings = DEFAULT_SETTINGS,
) -> dict | None:
    """Simulate one long trade using bars after the signal bar."""
    if signal_index + 1 >= len(bars):
        return None

    entry_bar = bars.iloc[signal_index + 1]
    entry_date = bars.index[signal_index + 1]
    entry = float(entry_bar["Open"])

    stop = float(signal["stop"])

    if entry <= stop:
        return None

    risk_per_share = entry - stop
    target = entry + settings.target_r_multiple * risk_per_share

    exit_price = None
    exit_date = None
    exit_reason = None

    last_index = min(
        signal_index + settings.maximum_holding_days,
        len(bars) - 1,
    )

    for index in range(signal_index + 1, last_index + 1):
        bar = bars.iloc[index]
        date = bars.index[index]

        # A gap through the stop is modeled at the open.
        if float(bar["Open"]) <= stop:
            exit_price = float(bar["Open"])
            exit_date = date
            exit_reason = "gap_stop"
            break

        # A gap through the target is conservatively modeled at target.
        if float(bar["Open"]) >= target:
            exit_price = target
            exit_date = date
            exit_reason = "target_gap"
            break

        hit_stop = float(bar["Low"]) <= stop
        hit_target = float(bar["High"]) >= target

        # Without intraday data, the sequence is unknowable.
        if hit_stop:
            exit_price = stop
            exit_date = date
            exit_reason = "stop"
            break

        if hit_target:
            exit_price = target
            exit_date = date
            exit_reason = "target"
            break

        if index == last_index:
            exit_price = float(bar["Close"])
            exit_date = date
            exit_reason = "time_exit"

    if exit_price is None:
        return None

    # Simple per-share slippage approximation on entry and exit.
    slippage = settings.slippage_bps / 10_000
    effective_entry = entry * (1 + slippage)
    effective_exit = exit_price * (1 - slippage)

    gross_return = effective_exit - effective_entry
    net_return = gross_return - 2 * settings.commission_per_share

    return {
        "ticker": signal["ticker"],
        "strategy": signal["strategy"],
        "signal_date": str(bars.index[signal_index].date()),
        "entry_date": str(entry_date.date()),
        "exit_date": str(exit_date.date()),
        "entry": entry,
        "exit": exit_price,
        "stop": stop,
        "target": target,
        "exit_reason": exit_reason,
        "net_pnl_per_share": net_return,
        "net_r_multiple": net_return / risk_per_share,
    }


def backtest_ticker(
    ticker: str,
    bars: pd.DataFrame,
    benchmark_close: pd.Series,
    settings: Settings = DEFAULT_SETTINGS,
) -> pd.DataFrame:
    """Generate historical candidates and simulate subsequent entries."""
    features = calculate_features(
        bars,
        benchmark_close=benchmark_close,
        settings=settings,
    )

    benchmark_features = calculate_features(
        pd.DataFrame(
            {
                "Open": benchmark_close,
                "High": benchmark_close,
                "Low": benchmark_close,
                "Close": benchmark_close,
                "Volume": 1,
            },
            index=benchmark_close.index,
        ),
        settings=settings,
    )

    trades = []

    # Only evaluate bars for which a next-session entry exists.
    for index in range(settings.minimum_history, len(bars) - 1):
        history = features.iloc[: index + 1]

        benchmark_row = benchmark_features.reindex(
            history.index
        ).iloc[-1]

        benchmark_uptrend = (
            pd.notna(benchmark_row["EMA20"])
            and pd.notna(benchmark_row["SMA50"])
            and benchmark_row["Close"] > benchmark_row["EMA20"]
            and benchmark_row["EMA20"] > benchmark_row["SMA50"]
        )

        signals = generate_signals(
            ticker,
            history,
            settings,
            benchmark_uptrend=benchmark_uptrend,
        )

        for signal in signals:
            trade = simulate_trade(
                bars,
                index,
                signal,
                settings,
            )
            if trade:
                trades.append(trade)

    return pd.DataFrame(trades)


def summarize_trades(trades: pd.DataFrame) -> dict:
    """Return basic trade statistics; these are not proof of an edge."""
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "average_r": 0.0,
            "profit_factor": 0.0,
        }

    returns = trades["net_pnl_per_share"]
    winners = returns[returns > 0]
    losers = returns[returns < 0]

    gross_profit = float(winners.sum())
    gross_loss = abs(float(losers.sum()))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf") if gross_profit > 0 else 0.0
    )

    return {
        "trades": int(len(trades)),
        "win_rate": float((returns > 0).mean()),
        "average_r": float(trades["net_r_multiple"].mean()),
        "profit_factor": profit_factor,
    }
