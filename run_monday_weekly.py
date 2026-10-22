"""Daily entries, maximum five trading sessions; legacy filename retained for launcher compatibility."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import pandas as pd
from run_reclaim_lab import TRIALS, setup, portfolio_summary


def simulate_max_hold(windows, market, mode, bps):
    if not windows or mode not in TRIALS or bps not in (5,15):
        raise ValueError("Invalid trial")
    dates = next(iter(windows.values())).index
    if (len(dates) != 15 or dates.has_duplicates or not dates.is_monotonic_increasing
            or not market.index.equals(dates) or any(not x.index.equals(dates) for x in windows.values())):
        raise ValueError("All inputs must share fifteen ordered unique sessions")
    columns = ["ticker", "strategy", "signal_date", "entry_date", "exit_date", "exit_reason", "entry_fill", "exit_fill", "stop", "target", "shares", "equity_before", "allocation_budget", "risk_budget", "position_cost", "planned_stop_risk", "net_pnl", "equity_after", "held_sessions", "held_calendar_days"]
    equity, last_exit, rows = 1000.0, -1, []
    counts = dict(eligible_entry_dates=0, occupied_entry_dates=0, no_setup_candidates=0,
        invalid_open_candidates=0, no_chase_rejections=0, unaffordable_candidate_events=0, risk_size_rejections=0)
    slip = bps/10000.0
    for i in range(3, len(dates)-1):
        entry_i = i+1
        if entry_i <= last_exit:
            counts["occupied_entry_dates"] += 1
            continue
        if equity <= 0:
            break
        counts["eligible_entry_dates"] += 1
        for ticker in sorted(windows):
            frame = windows[ticker]
            signal = setup(frame.iloc[:i+1], mode, market.iloc[:i+1])
            if signal is None:
                counts["no_setup_candidates"] += 1
                continue
            entry, stop = float(frame.iloc[entry_i].Open), signal["stop"]
            if entry <= stop:
                counts["invalid_open_candidates"] += 1
                continue
            if signal["max_open"] is not None and entry > signal["max_open"]:
                counts["no_chase_rejections"] += 1
                continue
            entry_fill = entry*(1+slip)
            allocation_budget, risk_budget = equity*0.25, equity*0.25*0.06
            unit_risk = entry_fill-stop*(1-slip)
            affordable = math.floor(allocation_budget/entry_fill)
            if affordable < 1:
                counts["unaffordable_candidate_events"] += 1
                continue
            shares = min(affordable, math.floor(risk_budget/unit_risk))
            if shares < 1:
                counts["risk_size_rejections"] += 1
                continue
            target = entry+2*(entry-stop)
            intended = entry_i+4
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
                    price, reason = float(bar.Close), "window_end" if intended > final else "five_session_exit"
                else:
                    continue
                break
            exit_fill = price*(1-slip)
            pnl = shares*(exit_fill-entry_fill)
            before, equity = equity, equity+pnl
            rows.append(dict(ticker=ticker, strategy=mode, signal_date=str(dates[i].date()),
                entry_date=str(dates[entry_i].date()), exit_date=str(dates[j].date()), exit_reason=reason,
                entry_fill=entry_fill, exit_fill=exit_fill, stop=stop, target=target, shares=shares,
                equity_before=before, allocation_budget=allocation_budget, risk_budget=risk_budget,
                position_cost=shares*entry_fill, planned_stop_risk=shares*unit_risk,
                net_pnl=pnl, equity_after=equity, held_sessions=j-entry_i+1,
                held_calendar_days=int((dates[j]-dates[entry_i]).days)))
            last_exit = j
            break
    journal = pd.DataFrame(rows, columns=columns)
    pnl = journal.net_pnl.astype(float)
    forced = journal.exit_reason.eq("window_end")
    streak = longest = 0
    for value in pnl:
        streak = streak+1 if value < 0 else 0
        longest = max(longest, streak)
    curve = pd.Series([1000.0]+journal.equity_after.tolist(), dtype=float)
    summary = dict(strategy=mode, hold=5, sessions=15, bps_per_side=bps, starting_equity=1000.0,
        final_equity=equity, trades=len(rows), net_pnl=float(pnl.sum()), return_pct=(equity/1000-1)*100,
        wins=int((pnl > 0).sum()), losses=int((pnl < 0).sum()), breakeven=int((pnl == 0).sum()),
        win_rate_pct=float((pnl > 0).mean()*100) if rows else None, max_consecutive_losses=longest,
        average_held_sessions=float(journal.held_sessions.mean()) if rows else None,
        shortest_hold_sessions=int(journal.held_sessions.min()) if rows else None,
        longest_hold_sessions=int(journal.held_sessions.max()) if rows else None,
        average_held_calendar_days=float(journal.held_calendar_days.mean()) if rows else None,
        normal_exit_pnl=float(pnl[~forced].sum()), window_end_pnl=float(pnl[forced].sum()), window_end_exits=int(forced.sum()),
        closed_trade_drawdown_pct=float(((curve.cummax()-curve)/curve.cummax()).max()*100), **counts)
    return journal, summary


def main():
    import yfinance as yf
    from swingbot.scanner import load_tickers
    from swingbot.short_history import prepare_window
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asof", default=str(pd.Timestamp.now(tz="America/New_York").date()), help="Exclusive cutoff")
    parser.add_argument("--output", default="reports/monday_weekly_hold")
    args = parser.parse_args()
    cutoff = pd.Timestamp(args.asof).tz_localize(None).normalize()
    if cutoff > pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize():
        raise ValueError("Future cutoff prohibited")
    tickers = sorted(set(load_tickers("config/tickers.txt")))
    if not tickers:
        raise ValueError("Empty universe")
    inputs = {}
    for ticker in sorted(set(tickers) | {"SPY"}):
        raw = yf.Ticker(ticker).history(start=str((cutoff-pd.Timedelta(days=60)).date()), end=str(cutoff.date()), interval="1d", auto_adjust=True, actions=False, raise_errors=True)
        inputs[ticker] = prepare_window(raw, cutoff, sessions=15)
    dates = inputs["SPY"].index
    if any(not x.index.equals(dates) for x in inputs.values()):
        raise ValueError("Mismatched input sessions; no silent exclusions")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    coverage, results = {}, []
    for number, ticker in enumerate(sorted(inputs)):
        snapshot = inputs[ticker].to_csv(index_label="Date")
        filename = f"bars_{number:04d}.csv"
        (output/filename).write_text(snapshot, encoding="utf-8")
        coverage[ticker] = dict(file=filename, sha256=hashlib.sha256(snapshot.encode()).hexdigest())
    windows = {ticker: inputs[ticker] for ticker in tickers}
    for mode in TRIALS:
        for bps in (15,5):
            journal, result = simulate_max_hold(windows, inputs["SPY"], mode, bps)
            journal.to_csv(output/f"{mode}_max5_bps{bps}_journal.csv", index=False)
            results.append(result)
    table = pd.DataFrame(results).sort_values(["bps_per_side", "net_pnl"], ascending=[False,False])
    table.to_csv(output/"all_trials.csv", index=False)
    limitations = "Daily next-open entries, no weekday restrictions. Maximum five trading sessions, entry counted as session one. Stops/targets may exit earlier. Truncated final-window trades close at the last retained close and are labeled window_end, not normal five-session exits. Fifteen retained sessions only, no older signal warmup or independent holdout. Whole shares, no leverage, zero commission/cash interest. Current-universe and stop-first daily-bar limitations remain. Separate accounts, not combined portfolios."
    manifest = dict(experiment="daily_entry_max_five_sessions", exclusive_cutoff=str(cutoff.date()), retained_sessions=[str(x.date()) for x in dates],
        starting_equity=1000, allocation_pct=25, risk_pct_of_allocation=6, initial_risk_budget=15, max_hold_sessions=5,
        universe=tickers, benchmark="SPY", coverage=coverage, trials=len(results), limitations=limitations, results=results)
    (output/"results.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    text = "# Daily-entry experiment — maximum five trading sessions\n\n"+limitations+"\n\n"
    text += "| Strategy | bps/side | Trades | Win rate | Forced exits | Forced P&L | Normal-exit P&L |\n|---|---:|---:|---:|---:|---:|---:|\n"
    for row in table.to_dict("records"):
        rate = "N/A" if pd.isna(row["win_rate_pct"]) else f"{row['win_rate_pct']:.1f}%"
        text += f"| {row['strategy']} | {row['bps_per_side']} | {row['trades']} | {rate} | {row['window_end_exits']} | {row['window_end_pnl']:+.2f} | {row['normal_exit_pnl']:+.2f} |\n"
    text += portfolio_summary(table)
    (output/"summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
