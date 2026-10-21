from __future__ import annotations

import numpy as np
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
    last_index = min(signal_index + settings.maximum_holding_days, len(bars) - 1)

    for index in range(signal_index + 1, last_index + 1):
        bar = bars.iloc[index]
        date = bars.index[index]
        if float(bar["Open"]) <= stop:
            exit_price, exit_date, exit_reason = float(bar["Open"]), date, "gap_stop"
            break
        if float(bar["Open"]) >= target:
            exit_price, exit_date, exit_reason = target, date, "target_gap"
            break
        if float(bar["Low"]) <= stop:
            exit_price, exit_date, exit_reason = stop, date, "stop"
            break
        if float(bar["High"]) >= target:
            exit_price, exit_date, exit_reason = target, date, "target"
            break
        if index == last_index:
            exit_price, exit_date, exit_reason = float(bar["Close"]), date, "time_exit"

    if exit_price is None:
        return None

    slippage = settings.slippage_bps / 10_000
    effective_entry = entry * (1 + slippage)
    effective_exit = exit_price * (1 - slippage)
    net_return = effective_exit - effective_entry - 2 * settings.commission_per_share
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
    """Generate independent trade observations, not a portfolio simulation."""
    features = calculate_features(bars, benchmark_close=benchmark_close, settings=settings)
    benchmark_features = calculate_features(
        pd.DataFrame({"Open": benchmark_close, "High": benchmark_close,
                      "Low": benchmark_close, "Close": benchmark_close, "Volume": 1},
                     index=benchmark_close.index),
        settings=settings,
    )
    trades = []
    for index in range(settings.minimum_history, len(bars) - 1):
        history = features.iloc[:index + 1]
        benchmark_row = benchmark_features.reindex(history.index).iloc[-1]
        benchmark_uptrend = (
            pd.notna(benchmark_row["EMA20"])
            and pd.notna(benchmark_row["SMA50"])
            and benchmark_row["Close"] > benchmark_row["EMA20"]
            and benchmark_row["EMA20"] > benchmark_row["SMA50"]
        )
        signals = generate_signals(ticker, history, settings,
                                   benchmark_uptrend=benchmark_uptrend)
        for signal in signals:
            trade = simulate_trade(bars, index, signal, settings)
            if trade:
                trades.append(trade)
    return pd.DataFrame(trades)


def summarize_trades(trades: pd.DataFrame) -> dict:
    """Return JSON-safe independent-trade statistics, not portfolio returns.

    Profit factor uses one share per trade. A profitable sample with no
    losses has no finite profit factor; represent it with None, not infinity.
    Invalid observations fail loudly rather than disappearing from metrics.
    """
    basis = "one_share_per_trade_not_portfolio"
    if trades.empty:
        return {
            "trades": 0, "win_rate": 0.0, "average_r": 0.0,
            "profit_factor": 0.0, "profit_factor_status": "no_trades",
            "profit_factor_basis": basis,
        }

    required = ["net_pnl_per_share", "net_r_multiple"]
    missing = set(required) - set(trades.columns)
    if missing:
        raise ValueError(f"Missing trade columns: {sorted(missing)}")
    values = trades[required].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("Trade statistics require finite numeric P&L and R values.")

    returns = values["net_pnl_per_share"]
    gross_profit = float(returns.clip(lower=0).sum())
    gross_loss = float(-returns.clip(upper=0).sum())
    if not np.isfinite([gross_profit, gross_loss]).all():
        raise ValueError("Aggregate trade P&L exceeds the finite numeric range.")

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
        if not np.isfinite(profit_factor):
            profit_factor, status = None, "numeric_overflow"
        else:
            status = "finite"
    elif gross_profit > 0:
        profit_factor, status = None, "no_losing_trades"
    else:
        profit_factor, status = 0.0, "all_breakeven"

    average_r = float(values["net_r_multiple"].mean())
    if not np.isfinite(average_r):
        raise ValueError("Average R exceeds the finite numeric range.")
    return {
        "trades": int(len(trades)),
        "win_rate": float((returns > 0).mean()),
        "average_r": average_r,
        "profit_factor": profit_factor,
        "profit_factor_status": status,
        "profit_factor_basis": basis,
    }
