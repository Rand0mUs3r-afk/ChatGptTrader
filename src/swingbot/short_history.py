"""Short-history hypotheses and one-position cash-funded daily-bar replay."""
import math

import pandas as pd

BASE = ("breakout3", "momentum3", "reversal2", "dip_rebound3", "inside_breakout")
MODES = BASE + ("union", "consensus")
TRADE_COLUMNS = ["ticker", "mode", "signal_date", "entry_date", "exit_date", "shares", "entry", "stop", "target", "exit", "net_pnl", "exit_reason", "reason"]


def choose_signal(history, mode):
    if mode not in MODES:
        raise ValueError("Unknown short-history mode")
    if len(history) < 4:
        return None
    row, previous, older = history.iloc[-1], history.iloc[-2], history.iloc[-3]
    prior = history.iloc[-4:-1]
    close = float(row["Close"])
    span = float((prior["High"] - prior["Low"]).mean())
    if span <= 0 or close < 5 or row["Volume"] <= 0:
        return None
    rules = {
        "breakout3": close > prior["High"].max() and close > row["Open"],
        "momentum3": close > prior["Close"].iloc[0] and close > previous["Close"],
        "reversal2": previous["Close"] < older["Close"] and close > previous["High"] and close > row["Open"],
        "dip_rebound3": close < prior["Close"].mean() - 0.5 * span and close > row["Open"],
        "inside_breakout": previous["High"] < older["High"] and previous["Low"] > older["Low"] and close > previous["High"] and close > row["Open"],
    }
    matched = [name for name in BASE if rules[name]]
    if not matched or (mode in BASE and mode not in matched) or (mode == "consensus" and len(matched) < 2):
        return None
    stop = float(history["Low"].iloc[-3:].min()) - 0.1 * span
    if not 0 < stop < close:
        return None
    source = mode if mode in BASE else matched[0]
    return dict(stop=stop, signal_date=str(history.index[-1].date()),
                reason=f"{mode}: matched {', '.join(matched)}; fixed priority source={source}; "
                       f"close={close:.4f}, prior high3={prior['High'].max():.4f}, "
                       f"prior mean3={prior['Close'].mean():.4f}, prior average range3={span:.4f}. "
                       "Union accepts any; consensus requires at least two correlated rules, not independent votes.")


def run_trial(panel, mode, hold, settings):
    if mode not in MODES or hold not in (1, 2, 3) or not panel:
        raise ValueError("Invalid trial")
    dates = next(iter(panel.values())).index
    if len(dates) < 5 or not dates.is_monotonic_increasing or dates.has_duplicates:
        raise ValueError("Need at least five sorted unique sessions")
    for ticker, frame in panel.items():
        if not frame.index.equals(dates):
            raise ValueError(f"Session mismatch: {ticker}")
        prices = frame[["Open", "High", "Low", "Close", "Volume"]].astype(float)
        if not all(math.isfinite(v) for v in prices.to_numpy().flat):
            raise ValueError("Nonfinite market data")
        if ((prices[["Open", "High", "Low", "Close"]] <= 0).any().any()
                or (prices["Volume"] < 0).any()
                or (prices["High"] < prices[["Open", "Close", "Low"]].max(axis=1)).any()
                or (prices["Low"] > prices[["Open", "Close", "High"]].min(axis=1)).any()):
            raise ValueError("Invalid OHLCV data")
    cash = float(settings.account_equity)
    risk, cap = float(settings.risk_fraction), float(settings.maximum_position_fraction)
    slip, fee = float(settings.slippage_bps) / 10000, float(settings.commission_per_share)
    if not all(math.isfinite(v) for v in (cash, risk, cap, slip, fee)) or cash <= 0 or not 0 < risk <= 0.02 or not 0 < cap <= 1 or not 0 <= slip < 1 or fee < 0:
        raise ValueError("Invalid account or cost settings")
    starting, position, entered, skipped = cash, None, 0, 0
    closed, curve = [], []
    for index, date in enumerate(dates):
        candidates = []
        if index >= 4:
            for ticker in sorted(panel):
                signal = choose_signal(panel[ticker].iloc[:index], mode)
                if signal is not None:
                    candidates.append((ticker, signal))
        if position is not None:
            skipped += len(candidates)
        else:
            for number, (ticker, signal) in enumerate(candidates):
                entry = float(panel[ticker].iloc[index]["Open"])
                stop = signal["stop"]
                entry_cost = entry * (1 + slip) + fee
                stop_proceeds = stop * (1 - slip) - fee
                if entry <= stop:
                    skipped += 1
                    continue
                shares = min(math.floor(cash * risk / (entry_cost - stop_proceeds)), math.floor(cash * cap / entry_cost))
                if shares <= 0:
                    skipped += 1
                    continue
                cash -= shares * entry_cost
                position = dict(ticker=ticker, mode=mode, signal_date=signal["signal_date"],
                    entry_date=str(date.date()), shares=shares, entry=entry, stop=stop,
                    target=entry + 2 * (entry - stop), entry_cost=entry_cost, entry_index=index,
                    reason=signal["reason"] + " Portfolio picks first eligible ticker alphabetically; one position; risk/cash caps.")
                entered += 1
                skipped += len(candidates) - number - 1
                break
        if position is not None:
            bar = panel[position["ticker"]].iloc[index]
            op, hi, lo = float(bar["Open"]), float(bar["High"]), float(bar["Low"])
            stop, target = position["stop"], position["target"]
            exit_price, why = None, None
            if op <= stop:
                exit_price, why = op, "gap_stop"
            elif op >= target:
                exit_price, why = target, "target_gap"
            elif lo <= stop:
                exit_price, why = stop, "stop"
            elif hi >= target:
                exit_price, why = target, "target"
            elif index - position["entry_index"] + 1 >= hold:
                exit_price, why = float(bar["Close"]), "time_exit"
            if exit_price is not None:
                proceeds = exit_price * (1 - slip) - fee
                pnl = position["shares"] * (proceeds - position["entry_cost"])
                cash += position["shares"] * proceeds
                record = {key: position[key] for key in TRADE_COLUMNS if key in position}
                record.update(exit_date=str(date.date()), exit=exit_price, net_pnl=pnl, exit_reason=why)
                closed.append(record)
                position = None
        marked = 0.0 if position is None else position["shares"] * float(panel[position["ticker"]].iloc[index]["Close"])
        equity = cash + marked
        if not math.isfinite(equity):
            raise ValueError("Nonfinite account equity")
        curve.append(dict(date=str(date.date()), cash=cash, market_value=marked, equity=equity))
    journal = pd.DataFrame(closed, columns=TRADE_COLUMNS)
    daily = pd.DataFrame(curve)
    peak = daily["equity"].cummax().clip(lower=starting)
    dd = (peak - daily["equity"]) / peak * 100
    pnls = [trade["net_pnl"] for trade in closed]
    winning = sum(v > 0 for v in pnls)
    losing = sum(v < 0 for v in pnls)
    win_run = loss_run = max_win = max_loss = 0
    for value in pnls:
        win_run = win_run + 1 if value > 0 else 0
        loss_run = loss_run + 1 if value < 0 else 0
        max_win, max_loss = max(max_win, win_run), max(max_loss, loss_run)
    open_rows = []
    if position is not None:
        mark = float(panel[position["ticker"]].iloc[-1]["Close"])
        row = {k: v for k, v in position.items() if k != "entry_index"}
        row.update(mark_date=str(dates[-1].date()), mark_price=mark,
                   unrealized_pnl=position["shares"] * (mark - position["entry_cost"]))
        open_rows.append(row)
    realized = float(sum(pnls))
    unrealized = float(sum(row["unrealized_pnl"] for row in open_rows))
    summary = dict(mode=mode, hold=hold, slippage_bps=settings.slippage_bps,
        starting_equity=starting, final_equity=float(daily.iloc[-1]["equity"]),
        realized_pnl=realized, unrealized_pnl=unrealized,
        return_pct=(float(daily.iloc[-1]["equity"]) / starting - 1) * 100,
        trades_entered=entered, closed_trades=len(closed), open_positions=len(open_rows),
        wins=winning, losses=losing, breakeven=len(closed)-winning-losing,
        win_rate_pct=winning / len(closed) * 100 if closed else None,
        loss_rate_pct=losing / len(closed) * 100 if closed else None,
        total_money_won=float(sum(v for v in pnls if v > 0)),
        total_money_lost=float(-sum(v for v in pnls if v < 0)),
        max_consecutive_wins=max_win, max_consecutive_losses=max_loss,
        max_daily_close_drawdown_pct=float(dd.max()), skipped_candidates=skipped)
    return journal, pd.DataFrame(open_rows), daily, summary
