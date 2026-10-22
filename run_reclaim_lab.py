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


def simulate(windows, market, mode, bps, starting=25000.0, allocation=0.20, risk_fraction=0.025):
    """Legacy defaults retained for comparisons; main explicitly uses 1000/25%/6%."""
    if (mode not in TRIALS or bps not in (5, 15) or not math.isfinite(starting) or starting <= 0 or not windows
            or not math.isfinite(allocation) or not 0 < allocation <= 1
            or not math.isfinite(risk_fraction) or not 0 < risk_fraction <= 1):
        raise ValueError("Invalid trial")
    dates = next(iter(windows.values())).index
    if len(dates) not in (5, 15) or not market.index.equals(dates) or any(not x.index.equals(dates) for x in windows.values()):
        raise ValueError("Identical five or fifteen sessions required for every input")
    columns = ["ticker", "strategy", "signal_date", "entry_date", "exit_date", "entry", "entry_fill", "exit", "exit_fill", "stop", "target", "shares", "net_pnl", "equity_after", "exit_reason", "equity_before", "allocation_budget", "risk_budget", "position_cost", "planned_stop_risk", "held_sessions", "held_calendar_days"]
    hold, equity, last_exit, rows = TRIALS[mode], float(starting), -1, []
    unaffordable = 0
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
            allocation_budget = equity*allocation
            risk_budget = allocation_budget*risk_fraction
            unit_risk = entry_fill-stop*(1-slip)
            affordable = math.floor(allocation_budget/entry_fill)
            if affordable < 1:
                unaffordable += 1
            shares = min(math.floor(risk_budget/unit_risk), affordable)
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
            before, equity = equity, equity+pnl
            rows.append(dict(ticker=ticker, strategy=mode, signal_date=str(dates[i].date()), entry_date=str(dates[entry_i].date()),
                exit_date=str(dates[j].date()), entry=entry, entry_fill=entry_fill, exit=price, exit_fill=exit_fill,
                stop=stop, target=target, shares=shares, net_pnl=pnl, equity_after=equity, exit_reason=reason,
                equity_before=before, allocation_budget=allocation_budget, risk_budget=risk_budget,
                position_cost=shares*entry_fill, planned_stop_risk=shares*unit_risk,
                held_sessions=j-entry_i+1, held_calendar_days=int((dates[j]-dates[entry_i]).days)))
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
        allocation_pct=allocation*100, risk_pct_of_allocation=risk_fraction*100, initial_risk_budget=starting*allocation*risk_fraction,
        wins=len(wins), losses=len(losses), breakeven=int((pnl == 0).sum()),
        win_rate_pct=float((pnl > 0).mean()*100) if rows else None,
        average_win=float(wins.mean()) if len(wins) else None, average_loss=float(losses.mean()) if len(losses) else None,
        largest_gain=float(wins.max()) if len(wins) else None, largest_loss=float(losses.min()) if len(losses) else None,
        average_trade=float(pnl.mean()) if rows else None, max_consecutive_losses=longest,
        average_held_sessions=float(journal.held_sessions.mean()) if rows else None,
        shortest_hold_sessions=int(journal.held_sessions.min()) if rows else None,
        longest_hold_sessions=int(journal.held_sessions.max()) if rows else None,
        average_held_calendar_days=float(journal.held_calendar_days.mean()) if rows else None,
        unaffordable_candidate_events=unaffordable,
        normal_exit_pnl=float(pnl[~forced].sum()), window_end_pnl=float(pnl[forced].sum()), window_end_exits=int(forced.sum()),
        closed_trade_drawdown_pct=float(((curve.cummax()-curve)/curve.cummax()).max()*100))
    return journal, summary


def portfolio_summary(table):
    text = "\n---\n## Final portfolio summary — separate accounts, never combined\n\n"
    text += "Starting equity: $1,000 per trial. Allocation cap: 25% of current equity. Planned risk ceiling: 6% of allocation budget (initially $15). Whole shares; no leverage. Actual risk may be lower; gaps can exceed planned risk.\n\n"
    text += "| Sessions | Strategy | bps/side | Total trades | Won | Lost | Breakeven | Final equity | Net P&L | Avg hold sessions | Shortest/longest | Avg calendar days |\n|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|\n"
    for row in table.to_dict("records"):
        active = row["trades"] > 0
        avg = f"{row['average_held_sessions']:.2f}" if active else "N/A"
        limits = f"{int(row['shortest_hold_sessions'])}/{int(row['longest_hold_sessions'])}" if active else "N/A"
        days = f"{row['average_held_calendar_days']:.2f}" if active else "N/A"
        text += f"| {row['sessions']} | {row['strategy']} | {row['bps_per_side']} | {row['trades']} | {row['wins']} | {row['losses']} | {row['breakeven']} | ${row['final_equity']:.2f} | {row['net_pnl']:+.2f} | {avg} | {limits} | {days} |\n"
    return text


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
                journal, summary = simulate(windows, inputs["SPY"].tail(sessions), mode, bps,
                    starting=1000.0, allocation=0.25, risk_fraction=0.06)
                journal.to_csv(output/f"s{sessions}_{mode}_bps{bps}_journal.csv", index=False)
                results.append(summary)
    table = pd.DataFrame(results).sort_values(["sessions", "bps_per_side", "net_pnl"], ascending=[False, False, False])
    table.to_csv(output/"all_trials.csv", index=False)
    limitations = "Exploratory, not validation. Five sessions overlap the fifteen-session sample. No older signal warmup. Four-bar readiness permits only one possible entry in five sessions. Current-universe bias, daily stop-first fills, zero commission, no cash interest. Forced exits are hypothetical. Drawdown is closed-trade only. No automatic winner deployment. Same-day exits count as one held session and zero calendar days."
    manifest = dict(cutoff_exclusive=str(cutoff.date()), sessions={str(n): [str(x.date()) for x in dates[-n:]] for n in (15, 5)},
        universe=tickers, benchmark="SPY", trials=len(results), coverage=coverage, limitations=limitations, results=results,
        portfolio=dict(starting_equity=1000, allocation_pct=25, risk_pct_of_allocation=6, initial_risk_budget=15, whole_shares=True))
    (output/"results.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    text = "# Frozen reclaim/compression experiment — $1,000 portfolio\n\n"+limitations+"\n\n"
    text += "| Sessions | Strategy | Hold | bps/side | Trades | Net P&L | Win rate | Loss streak | Forced exits | Forced P&L |\n|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for row in table.to_dict("records"):
        rate = "N/A" if pd.isna(row["win_rate_pct"]) else f"{row['win_rate_pct']:.1f}%"
        text += f"| {row['sessions']} | {row['strategy']} | {row['hold']} | {row['bps_per_side']} | {row['trades']} | {row['net_pnl']:+.2f} | {rate} | {row['max_consecutive_losses']} | {row['window_end_exits']} | {row['window_end_pnl']:+.2f} |\n"
    text += portfolio_summary(table)
    (output/"summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
