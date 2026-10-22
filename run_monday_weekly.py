"""Monday-only entries with Thursday/Friday scheduled exits; research only."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import pandas as pd
from run_reclaim_lab import TRIALS, setup, portfolio_summary


def week_schedule(dates):
    schedule = []
    for date in dates:
        if date.weekday() != 0:
            continue
        expected = pd.bdate_range(date, periods=5)
        previous_friday = date-pd.Timedelta(days=3)
        item = dict(monday=str(date.date()), eligible=False, reason="incomplete_or_holiday_week")
        if expected.isin(dates).all():
            item["reason"] = "missing_previous_friday"
            if previous_friday in dates:
                signal_i = int(dates.get_loc(previous_friday))
                item["reason"] = "insufficient_retained_signal_history"
                if signal_i >= 3:
                    item.update(eligible=True, reason="eligible", signal_index=signal_i,
                        entry_index=int(dates.get_loc(date)), thursday_index=int(dates.get_loc(expected[3])),
                        friday_index=int(dates.get_loc(expected[4])))
        schedule.append(item)
    return schedule


def simulate_weekly(windows, market, mode, exit_day, bps):
    if not windows or mode not in TRIALS or exit_day not in ("Thursday", "Friday") or bps not in (5,15):
        raise ValueError("Invalid weekly trial")
    dates = next(iter(windows.values())).index
    if (len(dates) != 15 or dates.has_duplicates or not dates.is_monotonic_increasing
            or not market.index.equals(dates) or any(not x.index.equals(dates) for x in windows.values())):
        raise ValueError("All inputs must share fifteen ordered unique sessions")
    columns = ["ticker", "strategy", "scheduled_exit_day", "signal_date", "entry_date", "scheduled_exit_date", "exit_date", "exit_reason", "entry_fill", "exit_fill", "stop", "target", "shares", "equity_before", "allocation_budget", "risk_budget", "position_cost", "planned_stop_risk", "net_pnl", "equity_after", "held_sessions", "held_calendar_days"]
    equity, rows, unaffordable = 1000.0, [], 0
    slip = bps/10000.0
    schedule = week_schedule(dates)
    for week in schedule:
        if not week["eligible"] or equity <= 0:
            continue
        signal_i, entry_i = week["signal_index"], week["entry_index"]
        final = week["thursday_index" if exit_day == "Thursday" else "friday_index"]
        for ticker in sorted(windows):
            frame = windows[ticker]
            signal = setup(frame.iloc[:signal_i+1], mode, market.iloc[:signal_i+1])
            if signal is None:
                continue
            entry, stop = float(frame.iloc[entry_i].Open), signal["stop"]
            if entry <= stop or (signal["max_open"] is not None and entry > signal["max_open"]):
                continue
            entry_fill = entry*(1+slip)
            allocation_budget, risk_budget = equity*0.25, equity*0.25*0.06
            unit_risk = entry_fill-stop*(1-slip)
            affordable = math.floor(allocation_budget/entry_fill)
            unaffordable += int(affordable < 1)
            shares = min(affordable, math.floor(risk_budget/unit_risk))
            if shares < 1:
                continue
            target = entry+2*(entry-stop)
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
                    price, reason = float(bar.Close), "scheduled_weekday_exit"
                else:
                    continue
                break
            exit_fill = price*(1-slip)
            pnl = shares*(exit_fill-entry_fill)
            before, equity = equity, equity+pnl
            rows.append(dict(ticker=ticker, strategy=mode, scheduled_exit_day=exit_day,
                signal_date=str(dates[signal_i].date()), entry_date=str(dates[entry_i].date()),
                scheduled_exit_date=str(dates[final].date()), exit_date=str(dates[j].date()), exit_reason=reason,
                entry_fill=entry_fill, exit_fill=exit_fill, stop=stop, target=target, shares=shares,
                equity_before=before, allocation_budget=allocation_budget, risk_budget=risk_budget,
                position_cost=shares*entry_fill, planned_stop_risk=shares*unit_risk,
                net_pnl=pnl, equity_after=equity, held_sessions=j-entry_i+1,
                held_calendar_days=int((dates[j]-dates[entry_i]).days)))
            break
    journal = pd.DataFrame(rows, columns=columns)
    pnl = journal.net_pnl.astype(float)
    streak = longest = 0
    for value in pnl:
        streak = streak+1 if value < 0 else 0
        longest = max(longest, streak)
    curve = pd.Series([1000.0]+journal.equity_after.tolist(), dtype=float)
    summary = dict(strategy=f"{mode} / {exit_day}", base_strategy=mode, scheduled_exit_day=exit_day,
        hold=4 if exit_day == "Thursday" else 5, sessions=15, bps_per_side=bps,
        starting_equity=1000.0, final_equity=equity, trades=len(rows), net_pnl=float(pnl.sum()), return_pct=(equity/1000-1)*100,
        wins=int((pnl > 0).sum()), losses=int((pnl < 0).sum()), breakeven=int((pnl == 0).sum()),
        win_rate_pct=float((pnl > 0).mean()*100) if rows else None, max_consecutive_losses=longest,
        average_held_sessions=float(journal.held_sessions.mean()) if rows else None,
        shortest_hold_sessions=int(journal.held_sessions.min()) if rows else None,
        longest_hold_sessions=int(journal.held_sessions.max()) if rows else None,
        average_held_calendar_days=float(journal.held_calendar_days.mean()) if rows else None,
        normal_exit_pnl=float(pnl.sum()), window_end_pnl=0.0, window_end_exits=0,
        eligible_weeks=sum(x["eligible"] for x in schedule), skipped_weeks=sum(not x["eligible"] for x in schedule),
        unaffordable_candidate_events=unaffordable,
        closed_trade_drawdown_pct=float(((curve.cummax()-curve)/curve.cummax()).max()*100))
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
        for day in ("Thursday", "Friday"):
            for bps in (15,5):
                journal, result = simulate_weekly(windows, inputs["SPY"], mode, day, bps)
                journal.to_csv(output/f"{mode}_{day}_bps{bps}_journal.csv", index=False)
                results.append(result)
    table = pd.DataFrame(results).sort_values(["bps_per_side", "net_pnl"], ascending=[False,False])
    table.to_csv(output/"all_trials.csv", index=False)
    pd.DataFrame(week_schedule(dates)).to_csv(output/"week_eligibility.csv", index=False)
    limitations = "Monday-only entries; previous Friday signals; scheduled Thursday/Friday closes, unless stop/target exits earlier. Complete Monday-Friday weeks only, no shifted holiday entries and no window-end forced liquidation. Fifteen retained sessions only, no older warmup; very few eligible weeks. No independent holdout, live orders, commissions, cash interest, fractional shares or leverage. Current-universe bias and daily-bar stop-first assumptions remain. Separate accounts, not combined portfolios."
    manifest = dict(exclusive_cutoff=str(cutoff.date()), retained_sessions=[str(x.date()) for x in dates],
        starting_equity=1000, allocation_pct=25, risk_pct_of_allocation=6, initial_risk_budget=15,
        universe=tickers, benchmark="SPY", coverage=coverage, trials=len(results),
        week_schedule=week_schedule(dates), limitations=limitations, results=results)
    (output/"results.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    text = "# Monday-entry weekly-hold experiment\n\n"+limitations+"\n\n"
    text += "An untriggered Monday-to-Thursday position spans four sessions/three calendar days; Monday-to-Friday spans five sessions/four calendar days. Actual durations are in journals. Eligible weeks are listed separately; no signal means no trade.\n"
    text += portfolio_summary(table)
    (output/"summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
