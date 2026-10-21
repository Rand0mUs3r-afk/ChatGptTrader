"""Frozen reclaim/compression hypotheses; manual research, never live orders."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import pandas as pd

TRIALS = {"reversal2": 3, "inside_breakout": 2, "failed_reclaim": 2,
          "compression_breakout": 2, "reversal_no_chase": 3,
          "reversal_compression_union": 2, "market_gated_union": 2, "cash": 0}


def setup(history, mode, market):
    if mode not in TRIALS:
        raise ValueError("Unknown strategy")
    if len(history) < 4 or mode == "cash":
        return None
    row, prev, older = history.iloc[-1], history.iloc[-2], history.iloc[-3]
    prior = history.iloc[-4:-1]
    bull = row.Close > row.Open
    span = float(row.High-row.Low)
    baseline_stop = float(history.Low.iloc[-3:].min()-0.1*(history.High-history.Low).iloc[-3:].mean())
    reversal = bool(bull and prev.Close < prev.Open and row.Close > prev.High)
    inside = bool(bull and prev.High < older.High and prev.Low > older.Low and row.Close > prev.High)
    compression = bool(bull and prev.High-prev.Low < older.High-older.Low
                       and prev.High-prev.Low < history.iloc[-4].High-history.iloc[-4].Low
                       and row.Close > prev.High)
    reclaim = bool(bull and span > 0 and row.Low < prior.Low.min() < row.Close
                   and (row.Close-row.Low)/span >= 0.75)
    stop, passed, cap = baseline_stop, False, None
    if mode in ("reversal2", "reversal_no_chase"):
        passed = reversal
        if mode == "reversal_no_chase":
            cap = float(row.Close+0.5*span)
    elif mode == "inside_breakout":
        passed = inside
    elif mode == "failed_reclaim":
        passed, stop = reclaim, float(row.Low-0.1*span)
    elif mode == "compression_breakout":
        passed, stop = compression, float(prev.Low-0.1*(prev.High-prev.Low))
    else:
        passed = reversal or compression
        if not reversal:
            stop = float(prev.Low-0.1*(prev.High-prev.Low))
        if mode == "market_gated_union":
            passed = passed and len(market) >= 4 and market.Close.iloc[-1] > market.Close.iloc[-4]
    if not passed or not 0 < stop < row.Close:
        return None
    return dict(stop=stop, max_open=cap)


def simulate(windows, market, mode, bps, starting=25000.0):
    if mode not in TRIALS or bps not in (5, 15) or not math.isfinite(starting) or starting <= 0 or not windows:
        raise ValueError("Invalid trial")
    dates = next(iter(windows.values())).index
    if len(dates) not in (5, 15) or not market.index.equals(dates) or any(not x.index.equals(dates) for x in windows.values()):
        raise ValueError("Identical five or fifteen sessions required for every input")
    columns = ["ticker", "strategy", "signal_date", "entry_date", "exit_date", "entry", "entry_fill", "exit", "exit_fill", "stop", "target", "shares", "net_pnl", "equity_after", "exit_reason"]
    hold, equity, last_exit, rows = TRIALS[mode], float(starting), -1, []
    slip = bps/10000.0
    for i in range(3, len(dates)-1):
        entry_i = i+1
        if entry_i <= last_exit or equity <= 0:
            continue
        for ticker in sorted(windows):
            frame = windows[ticker]
            signal = setup(frame.iloc[:i+1], mode, market.iloc[:i+1])
            if signal is None:
                continue
            entry, stop = float(frame.iloc[entry_i].Open), signal["stop"]
            if entry <= stop or (signal["max_open"] is not None and entry > signal["max_open"]):
                continue
            entry_fill = entry*(1+slip)
            shares = min(math.floor(equity*0.005/(entry_fill-stop*(1-slip))), math.floor(equity*0.20/entry_fill))
            if shares < 1:
                continue
            target = entry+2*(entry-stop)
            intended = entry_i+hold-1
            final = min(intended, len(dates)-1)
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
            exit_fill = price*(1-slip)
            pnl = shares*(exit_fill-entry_fill)
            equity += pnl
            rows.append(dict(ticker=ticker, strategy=mode, signal_date=str(dates[i].date()), entry_date=str(dates[entry_i].date()),
                exit_date=str(dates[j].date()), entry=entry, entry_fill=entry_fill, exit=price, exit_fill=exit_fill,
                stop=stop, target=target, shares=shares, net_pnl=pnl, equity_after=equity, exit_reason=reason))
            last_exit = j
            break
    journal = pd.DataFrame(rows, columns=columns)
    pnl = journal.net_pnl.astype(float)
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    forced = journal.exit_reason.eq("window_end")
    streak = longest = 0
    for value in pnl:
        streak = streak+1 if value < 0 else 0
        longest = max(longest, streak)
    curve = pd.Series([starting]+journal.equity_after.tolist(), dtype=float)
    summary = dict(strategy=mode, hold=hold, sessions=len(dates), bps_per_side=bps, trades=len(rows),
        starting_equity=starting, final_equity=equity, net_pnl=float(pnl.sum()), return_pct=(equity/starting-1)*100,
        wins=len(wins), losses=len(losses), breakeven=int((pnl == 0).sum()),
        win_rate_pct=float((pnl > 0).mean()*100) if rows else None,
        average_win=float(wins.mean()) if len(wins) else None, average_loss=float(losses.mean()) if len(losses) else None,
        largest_gain=float(wins.max()) if len(wins) else None, largest_loss=float(losses.min()) if len(losses) else None,
        average_trade=float(pnl.mean()) if rows else None, max_consecutive_losses=longest,
        normal_exit_pnl=float(pnl[~forced].sum()), window_end_pnl=float(pnl[forced].sum()), window_end_exits=int(forced.sum()),
        closed_trade_drawdown_pct=float(((curve.cummax()-curve)/curve.cummax()).max()*100))
    return journal, summary


def main():
    import yfinance as yf
    from swingbot.scanner import load_tickers
    from swingbot.short_history import prepare_window
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asof", default=str(pd.Timestamp.now(tz="America/New_York").date()), help="Exclusive date cutoff")
    parser.add_argument("--output", default="reports/reclaim_lab")
    args = parser.parse_args()
    cutoff = pd.Timestamp(args.asof).tz_localize(None).normalize()
    today = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
    if cutoff > today:
        raise ValueError("Future cutoffs prohibited")
    tickers = sorted(set(load_tickers("config/tickers.txt")))
    if not tickers:
        raise ValueError("Empty universe")
    inputs = {}
    for ticker in sorted(set(tickers) | {"SPY"}):
        raw = yf.Ticker(ticker).history(start=str((cutoff-pd.Timedelta(days=60)).date()), end=str(cutoff.date()), interval="1d", auto_adjust=True, actions=False, raise_errors=True)
        inputs[ticker] = prepare_window(raw, cutoff, sessions=15)
    dates = inputs["SPY"].index
    if any(not frame.index.equals(dates) for frame in inputs.values()):
        raise ValueError("Mismatched dates; no silent universe exclusions")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    coverage, results = {}, []
    for number, ticker in enumerate(sorted(inputs)):
        snapshot = inputs[ticker].to_csv(index_label="Date")
        filename = f"bars_{number:04d}.csv"
        (output/filename).write_text(snapshot, encoding="utf-8")
        coverage[ticker] = dict(file=filename, sha256=hashlib.sha256(snapshot.encode()).hexdigest())
    for sessions in (15, 5):
        windows = {ticker: inputs[ticker].tail(sessions) for ticker in tickers}
        for mode in TRIALS:
            for bps in (15, 5):
                journal, summary = simulate(windows, inputs["SPY"].tail(sessions), mode, bps)
                journal.to_csv(output/f"s{sessions}_{mode}_bps{bps}_journal.csv", index=False)
                results.append(summary)
    table = pd.DataFrame(results).sort_values(["sessions", "bps_per_side", "net_pnl"], ascending=[False, False, False])
    table.to_csv(output/"all_trials.csv", index=False)
    limitations = "Exploratory, not validation. Five sessions overlap the fifteen-session sample. No older signal warmup. Four-bar readiness permits only one possible entry in five sessions. Current-universe bias, daily stop-first fills, zero commission, no cash interest. Forced exits are hypothetical. Drawdown is closed-trade only. No automatic winner deployment."
    manifest = dict(cutoff_exclusive=str(cutoff.date()), sessions={str(n): [str(x.date()) for x in dates[-n:]] for n in (15, 5)},
        universe=tickers, benchmark="SPY", trials=len(results), coverage=coverage, limitations=limitations, results=results)
    (output/"results.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    text = "# Frozen reclaim/compression experiment\n\n"+limitations+"\n\n"
    text += "| Sessions | Strategy | Hold | bps/side | Trades | Net P&L | Win rate | Loss streak | Forced exits | Forced P&L |\n|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for row in table.to_dict("records"):
        rate = "N/A" if pd.isna(row["win_rate_pct"]) else f"{row['win_rate_pct']:.1f}%"
        text += f"| {row['sessions']} | {row['strategy']} | {row['hold']} | {row['bps_per_side']} | {row['trades']} | {row['net_pnl']:+.2f} | {rate} | {row['max_consecutive_losses']} | {row['window_end_exits']} | {row['window_end_pnl']:+.2f} |\n"
    (output/"summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
