"""Short-history hypotheses: analysis uses exactly 15 retained completed daily bars."""
import math

import pandas as pd

MODES = ("breakout3", "momentum3", "reversal2", "dip_rebound3", "inside_breakout", "momentum_union", "two_vote_blend")
TRADE_COLUMNS = ["ticker", "strategy", "signal_date", "entry_date", "exit_date", "entry", "exit", "stop", "target",
                 "shares", "net_pnl", "equity_before", "equity_after", "exit_reason", "window_end_exit", "reason"]


def prepare_window(bars, asof, sessions=15):
    """Drop current/future dates, retain the window BEFORE calculating any features."""
    frame = bars[["Open", "High", "Low", "Close", "Volume"]].copy()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    if frame.index.has_duplicates:
        raise ValueError("Duplicate daily sessions")
    cutoff = pd.Timestamp(asof).tz_localize(None).normalize()
    frame = frame.sort_index().loc[lambda data: data.index < cutoff].tail(sessions)
    if len(frame) != sessions:
        raise ValueError(f"Exactly {sessions} completed sessions required")
    frame = frame.apply(pd.to_numeric, errors="raise")
    if not all(math.isfinite(float(v)) for v in frame.to_numpy().flat):
        raise ValueError("Nonfinite market data")
    if ((frame[["Open", "High", "Low", "Close"]] <= 0).any().any() or (frame["Volume"] < 0).any()
            or (frame["Low"] > frame[["Open", "Close"]].min(axis=1)).any()
            or (frame["High"] < frame[["Open", "Close"]].max(axis=1)).any()):
        raise ValueError("Invalid OHLCV bars")
    return frame


def setups(history):
    """Signals use only the current completed bar and at most three previous bars."""
    if len(history) < 4:
        return {}
    row, prev, older = history.iloc[-1], history.iloc[-2], history.iloc[-3]
    prior = history.iloc[-4:-1]
    prior_mean, prior_std = prior["Close"].mean(), prior["Close"].std(ddof=0)
    checks = {
        "breakout3": row["Close"] > prior["High"].max() and row["Close"] > row["Open"],
        "momentum3": row["Close"] > prev["Close"] > older["Close"] and row["Close"] > row["Open"],
        "reversal2": prev["Close"] < prev["Open"] and row["Close"] > prev["High"] and row["Close"] > row["Open"],
        "dip_rebound3": prior_std > 0 and prev["Close"] < prior_mean - prior_std and row["Close"] > prev["Close"] and row["Close"] > row["Open"],
        "inside_breakout": prev["High"] < older["High"] and prev["Low"] > older["Low"] and row["Close"] > prev["High"] and row["Close"] > row["Open"],
    }
    passed = sorted(name for name, ok in checks.items() if ok)
    signals = {name: [name] for name in passed}
    momentum = [name for name in ("breakout3", "momentum3") if name in passed]
    if momentum:
        signals["momentum_union"] = momentum
    if len(passed) >= 2:
        signals["two_vote_blend"] = passed
    scale = (history["High"] - history["Low"]).iloc[-3:].mean()
    stop = float(history["Low"].iloc[-3:].min() - 0.1 * scale)
    if scale <= 0 or not 0 < stop < row["Close"]:
        return {}
    return {mode: dict(stop=stop, reason="Passed: " + ", ".join(votes) + f"; close={row['Close']:.4f}; prior3 high={prior['High'].max():.4f}; prior3 mean={prior_mean:.4f}; prior3 std={prior_std:.4f}") for mode, votes in signals.items()}


def simulate(windows, mode, hold, bps, starting=25000.0):
    """One position, deterministic ticker ordering, next-open fills, explicit window-end exits."""
    if mode not in MODES or hold not in (1, 2, 3) or bps not in (5.0, 15.0):
        raise ValueError("Unknown trial")
    dates = next(iter(windows.values())).index if windows else pd.DatetimeIndex([])
    if len(dates) != 15 or any(not frame.index.equals(dates) for frame in windows.values()):
        raise ValueError("All tickers must have the same 15 sessions")
    equity, last_exit, rows = float(starting), -1, []
    slip = bps / 10000
    for index in range(3, len(dates) - 1):
        entry_index = index + 1
        if entry_index <= last_exit or equity <= 0:
            continue
        for ticker in sorted(windows):
            bars = windows[ticker]
            signal = setups(bars.iloc[:index + 1]).get(mode)
            if signal is None:
                continue
            entry, stop = float(bars.iloc[entry_index]["Open"]), signal["stop"]
            if entry <= stop:
                continue
            entry_cost = entry * (1 + slip)
            risk_cost = entry_cost - stop * (1 - slip)
            shares = min(math.floor(equity * 0.005 / risk_cost), math.floor(equity * 0.20 / entry_cost))
            if shares < 1:
                continue
            target = entry + 2 * (entry - stop)
            final = min(entry_index + hold - 1, len(dates) - 1)
            for exit_index in range(entry_index, final + 1):
                bar = bars.iloc[exit_index]
                if bar["Open"] <= stop:
                    exit_price, reason = float(bar["Open"]), "gap_stop"
                elif bar["Open"] >= target:
                    exit_price, reason = target, "target_gap"
                elif bar["Low"] <= stop:
                    exit_price, reason = stop, "stop"
                elif bar["High"] >= target:
                    exit_price, reason = target, "target"
                elif exit_index == final:
                    exit_price = float(bar["Close"])
                    reason = "window_end" if entry_index + hold - 1 > final else "time_exit"
                else:
                    continue
                break
            pnl = shares * (exit_price * (1 - slip) - entry_cost)
            before, equity = equity, equity + pnl
            last_exit = exit_index
            rows.append(dict(ticker=ticker, strategy=mode, signal_date=str(dates[index].date()), entry_date=str(dates[entry_index].date()),
                exit_date=str(dates[exit_index].date()), entry=entry, exit=exit_price, stop=stop, target=target, shares=shares,
                net_pnl=pnl, equity_before=before, equity_after=equity, exit_reason=reason,
                window_end_exit=reason == "window_end", reason=signal["reason"] + "; first eligible ticker alphabetically; risk/notional limits applied"))
            break
    journal = pd.DataFrame(rows, columns=TRADE_COLUMNS)
    pnl = journal["net_pnl"].astype(float)
    win_run = loss_run = max_win = max_loss = 0
    for value in pnl:
        win_run = win_run + 1 if value > 0 else 0
        loss_run = loss_run + 1 if value < 0 else 0
        max_win, max_loss = max(max_win, win_run), max(max_loss, loss_run)
    curve = pd.Series([starting] + journal["equity_after"].tolist(), dtype=float)
    summary = dict(strategy=mode, hold=hold, slippage_bps=bps, starting_equity=starting, final_equity=equity,
        trades=len(rows), net_pnl=equity-starting, return_pct=(equity/starting-1)*100,
        wins=int((pnl>0).sum()), losses=int((pnl<0).sum()), breakeven=int((pnl==0).sum()),
        win_rate_pct=float((pnl>0).mean()*100) if rows else None, loss_rate_pct=float((pnl<0).mean()*100) if rows else None,
        total_money_won=float(pnl.clip(lower=0).sum()), total_money_lost=float(-pnl.clip(upper=0).sum()),
        max_consecutive_wins=max_win, max_consecutive_losses=max_loss,
        closed_trade_drawdown_pct=float(((curve.cummax()-curve)/curve.cummax()).max()*100),
        window_end_exits=int(journal["window_end_exit"].sum()))
    return journal, summary
