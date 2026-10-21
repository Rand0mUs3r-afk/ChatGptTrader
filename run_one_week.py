"""Manual five-completed-session research sandbox; no live orders or older warmup."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import pandas as pd

ORIGINAL = ("breakout3", "momentum3", "reversal2", "dip_rebound3", "inside_breakout")
FAST = ("fast_breakout", "fast_reversal", "fast_momentum", "bullish_engulfing", "close_strength")
BLENDS = ("momentum_union", "two_vote_blend", "recovery_union", "trend_confirm", "fast_two_vote", "reversal_inside_union")
MODES = ORIGINAL + FAST + BLENDS
COLUMNS = ("ticker", "strategy", "signal_date", "entry_date", "exit_date", "entry", "entry_fill", "exit", "exit_fill", "stop", "target", "shares", "net_pnl", "equity_before", "equity_after", "exit_reason", "votes")


def prepare_window(raw, asof):
    frame = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    if frame.index.has_duplicates:
        raise ValueError("Duplicate sessions")
    cutoff = pd.Timestamp(asof).tz_localize(None).normalize()
    frame = frame.sort_index().loc[lambda x: x.index < cutoff].tail(5)
    if len(frame) != 5:
        raise ValueError("Exactly five completed sessions required")
    frame = frame.apply(pd.to_numeric, errors="raise")
    if not all(math.isfinite(float(v)) for v in frame.to_numpy().flat):
        raise ValueError("Nonfinite OHLCV")
    if ((frame[["Open", "High", "Low", "Close"]] <= 0).any().any()
            or (frame.Volume < 0).any()
            or (frame.Low > frame[["Open", "Close"]].min(axis=1)).any()
            or (frame.High < frame[["Open", "Close"]].max(axis=1)).any()):
        raise ValueError("Invalid OHLCV")
    return frame


def signals(history):
    if len(history) < 2:
        return {}
    row, prev = history.iloc[-1], history.iloc[-2]
    bull = row.Close > row.Open
    spread = float(row.High - row.Low)
    strength = float((row.Close - row.Low) / spread) if spread > 0 else 0.0
    checks = dict(fast_breakout=bull and row.Close > prev.High,
        fast_reversal=bull and prev.Close < prev.Open and row.Close > prev.High,
        fast_momentum=bull and row.Close > prev.Close,
        bullish_engulfing=bull and prev.Close < prev.Open and row.Open <= prev.Close and row.Close >= prev.Open,
        close_strength=bull and strength >= 0.75)
    if len(history) >= 4:
        older, prior = history.iloc[-3], history.iloc[-4:-1]
        mean, std = prior.Close.mean(), prior.Close.std(ddof=0)
        checks.update(breakout3=bull and row.Close > prior.High.max(),
            momentum3=bull and row.Close > prev.Close > older.Close,
            reversal2=bull and prev.Close < prev.Open and row.Close > prev.High,
            dip_rebound3=bull and std > 0 and prev.Close < mean - std and row.Close > prev.Close,
            inside_breakout=bull and prev.High < older.High and prev.Low > older.Low and row.Close > prev.High)
    passed = {name for name, ok in checks.items() if ok}
    selected = {name: [name] for name in sorted(passed)}
    groups = {
        "momentum_union": (set(("breakout3", "momentum3")), 1),
        "two_vote_blend": (set(ORIGINAL), 2),
        "recovery_union": (set(("fast_reversal", "bullish_engulfing", "dip_rebound3")), 1),
        "trend_confirm": (set(("fast_momentum", "close_strength")), 2),
        "fast_two_vote": (set(FAST), 2),
        "reversal_inside_union": (set(("reversal2", "inside_breakout")), 1),
    }
    for name, (members, minimum) in groups.items():
        votes = sorted(passed & members)
        if len(votes) >= minimum:
            selected[name] = votes
    recent = history.iloc[-3:]
    scale = float((recent.High - recent.Low).mean())
    stop = float(recent.Low.min() - 0.1 * scale)
    if scale <= 0 or not 0 < stop < row.Close:
        return {}
    return {name: dict(stop=stop, votes=votes, strength=strength) for name, votes in selected.items()}


def simulate(windows, mode, hold, bps, starting=25000.0):
    if mode not in MODES or hold not in (1, 2, 3) or bps not in (5, 15) or starting <= 0:
        raise ValueError("Invalid trial")
    if not windows:
        raise ValueError("Empty universe")
    dates = next(iter(windows.values())).index
    if len(dates) != 5 or any(not x.index.equals(dates) for x in windows.values()):
        raise ValueError("All tickers must share exactly the same five sessions")
    equity, last_exit, rows = float(starting), -1, []
    slip = bps / 10000.0
    for i in range(1, 4):
        entry_i = i + 1
        if entry_i <= last_exit or equity <= 0:
            continue
        candidates = []
        for ticker, frame in windows.items():
            setup = signals(frame.iloc[:i+1]).get(mode)
            if setup:
                candidates.append((-len(setup["votes"]), -setup["strength"], ticker, setup))
        for _, _, ticker, setup in sorted(candidates, key=lambda x: x[:3]):
            frame, stop = windows[ticker], setup["stop"]
            entry = float(frame.iloc[entry_i].Open)
            if entry <= stop:
                continue
            entry_fill = entry * (1 + slip)
            risk = entry_fill - stop * (1 - slip)
            shares = min(math.floor(equity * 0.005 / risk), math.floor(equity * 0.20 / entry_fill))
            if shares < 1:
                continue
            target = entry + 2 * (entry - stop)
            intended = entry_i + hold - 1
            final = min(intended, 4)
            for j in range(entry_i, final+1):
                bar = frame.iloc[j]
                if bar.Open <= stop:
                    price, reason = float(bar.Open), "gap_stop"
                elif bar.Open >= target:
                    price, reason = target, "target_gap"
                elif bar.Low <= stop:
                    price, reason = stop, "stop"
                elif bar.High >= target:
                    price, reason = target, "target"
                elif j == final:
                    price, reason = float(bar.Close), "window_end" if intended > final else "time_exit"
                else:
                    continue
                break
            exit_fill = price * (1-slip)
            pnl = shares * (exit_fill-entry_fill)
            before, equity = equity, equity+pnl
            rows.append(dict(ticker=ticker, strategy=mode, signal_date=str(dates[i].date()),
                entry_date=str(dates[entry_i].date()), exit_date=str(dates[j].date()), entry=entry,
                entry_fill=entry_fill, exit=price, exit_fill=exit_fill, stop=stop, target=target, shares=shares,
                net_pnl=pnl, equity_before=before, equity_after=equity, exit_reason=reason, votes=",".join(setup["votes"])))
            last_exit = j
            break
    journal = pd.DataFrame(rows, columns=COLUMNS)
    pnl = journal.net_pnl.astype(float)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    forced = journal.exit_reason.eq("window_end")
    streak = longest = 0
    for value in pnl:
        streak = streak+1 if value < 0 else 0
        longest = max(longest, streak)
    curve = pd.Series([starting]+journal.equity_after.tolist(), dtype=float)
    summary = dict(strategy=mode, hold=hold, slippage_bps=bps, starting_equity=starting, final_equity=equity,
        trades=len(rows), wins=len(wins), losses=len(losses), breakeven=int((pnl == 0).sum()),
        net_pnl=float(pnl.sum()), return_pct=(equity/starting-1)*100,
        win_rate_pct=float((pnl > 0).mean()*100) if rows else None,
        average_win=float(wins.mean()) if len(wins) else None,
        average_loss=float(losses.mean()) if len(losses) else None,
        average_trade=float(pnl.mean()) if rows else None,
        largest_gain=float(wins.max()) if len(wins) else None,
        largest_loss=float(losses.min()) if len(losses) else None,
        max_consecutive_losses=longest, window_end_exits=int(forced.sum()),
        window_end_pnl=float(pnl[forced].sum()), normal_exit_pnl=float(pnl[~forced].sum()),
        closed_trade_drawdown_pct=float(((curve.cummax()-curve)/curve.cummax()).max()*100))
    return journal, summary


def main():
    import yfinance as yf
    from swingbot.scanner import load_tickers
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asof", default=str(pd.Timestamp.now(tz="America/New_York").date()), help="Exclusive cutoff date; current day always excluded")
    parser.add_argument("--tickers", default="config/tickers.txt")
    parser.add_argument("--output", default="reports/one_week_lab")
    args = parser.parse_args()
    cutoff = pd.Timestamp(args.asof).normalize()
    today = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
    if cutoff > today:
        raise ValueError("Cutoff cannot be in the future")
    tickers = sorted(set(load_tickers(args.tickers)))
    if not tickers:
        raise ValueError("Empty ticker list")
    windows = {}
    for ticker in tickers:
        raw = yf.Ticker(ticker).history(start=str((cutoff-pd.Timedelta(days=45)).date()), end=str(cutoff.date()), interval="1d", auto_adjust=True, actions=False, raise_errors=True)
        windows[ticker] = prepare_window(raw, cutoff)
    dates = windows[tickers[0]].index
    if any(not frame.index.equals(dates) for frame in windows.values()):
        raise ValueError("Mismatched sessions; no silent ticker exclusion")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    coverage, results = {}, []
    for number, ticker in enumerate(tickers):
        snapshot = windows[ticker].to_csv(index_label="Date")
        filename = f"bars_{number:04d}.csv"
        (output/filename).write_text(snapshot, encoding="utf-8")
        coverage[ticker] = dict(file=filename, bars=5, sha256=hashlib.sha256(snapshot.encode()).hexdigest())
    for mode in MODES:
        for hold in (1, 2, 3):
            for bps in (5, 15):
                journal, summary = simulate(windows, mode, hold, bps)
                journal.to_csv(output/f"{mode}_h{hold}_bps{bps}_journal.csv", index=False)
                results.append(summary)
    table = pd.DataFrame(results).sort_values(["slippage_bps", "net_pnl"], ascending=[False, False])
    table.to_csv(output/"all_trials.csv", index=False)
    manifest = dict(analysis_sessions=5, exclusive_cutoff=str(cutoff.date()), sessions=[str(x.date()) for x in dates],
        trials=len(results), coverage=coverage, results=results,
        limitations="No older indicator warmup. No independent holdout or live orders. Current-universe selection bias. At most three trade-entry dates; original rules only permit a final-day entry. Forced exits are hypothetical liquidation. Closed-trade drawdown is not daily mark-to-market. Blended votes are correlated, not independent confirmation. Sizing changes with costs. Ranking differs from the original alphabetical baseline.")
    (output/"results.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    text = "# Five-session strategy lab\n\n" + manifest["limitations"] + "\n\n"
    text += "| Strategy | Hold | bps/side | Trades | Net P&L | Win rate | Losing streak | Forced exits | Forced P&L |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for row in table.to_dict("records"):
        rate = "N/A" if pd.isna(row["win_rate_pct"]) else f"{row['win_rate_pct']:.1f}%"
        text += f"| {row['strategy']} | {row['hold']} | {row['slippage_bps']} | {row['trades']} | {row['net_pnl']:+.2f} | {rate} | {row['max_consecutive_losses']} | {row['window_end_exits']} | {row['window_end_pnl']:+.2f} |\n"
    (output/"summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
