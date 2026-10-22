"""Experimental structure/history targets. No orders or calibrated forecasts."""
import json
import math
import runpy
from pathlib import Path
import numpy as np
import pandas as pd

MIN_TRAIN, MIN_FORWARD, MIN_NET_RR, SLIP = 20, 10, 1.25, 0.0015


def net_rr(entry, stop, target):
    return (target*(1-SLIP)-entry*(1+SLIP))/(entry*(1+SLIP)-stop*(1-SLIP))


def propose(bars, entry, stop, past):
    if not 0 < stop < entry:
        raise ValueError("Invalid entry/stop")
    previous = bars.Close.shift()
    tr = pd.concat([bars.High-bars.Low, (bars.High-previous).abs(), (bars.Low-previous).abs()], axis=1).max(axis=1)
    atr = float(tr.iloc[-14:].mean()) if len(bars) >= 15 else None
    result = dict(atr14=atr, historical_examples=len(past), assessed_target=None,
                  assessed_net_rr=None, nearest_confirmed_high=None, target_in_atr=None)
    if atr is None or not math.isfinite(atr) or atr <= 0 or len(past) < MIN_TRAIN:
        return result
    highs = bars.High.to_numpy(dtype=float)
    pivots = [highs[j] for j in range(max(2,len(highs)-60),len(highs)-2)
        if highs[j] > max(highs[j-2:j]) and highs[j] > max(highs[j+1:j+3]) and highs[j] > entry]
    resistance = min(pivots) if pivots else None
    median_r = float(np.median([p["mfe_r"] for p in past]))
    target = entry + median_r*(entry-stop)
    if resistance is not None:
        target = min(target, resistance-0.1*atr)
    result.update(nearest_confirmed_high=float(resistance) if resistance is not None else None,
                  historical_median_mfe_r=median_r)
    if target > entry:
        result.update(assessed_target=float(target), assessed_net_rr=float(net_rr(entry,stop,target)),
                      target_in_atr=float((target-entry)/atr))
    return result


def trial(bars, signal_index, stop, hold, target=None):
    future = bars.iloc[signal_index+1:signal_index+hold+1]
    if len(future) != hold:
        raise ValueError("Unfinished horizon")
    entry = float(future.Open.iloc[0])
    if not 0 < stop < entry:
        return None
    mfe, exit_price, hit = 0.0, float(future.Close.iloc[-1]), False
    for bar in future.itertuples():
        o,h,l = float(bar.Open),float(bar.High),float(bar.Low)
        if o <= stop:
            exit_price = o
            break
        mfe = max(mfe, o-entry)
        if target is not None and o >= target:
            exit_price,hit = target,True
            break
        if l <= stop:
            exit_price = stop
            break
        mfe = max(mfe, h-entry)
        if target is not None and h >= target:
            exit_price,hit = target,True
            break
    risk = entry*(1+SLIP)-stop*(1-SLIP)
    return dict(entry=entry, mfe_r=max(0.0,mfe/(entry-stop)), target_hit=hit,
                net_r=(exit_price*(1-SLIP)-entry*(1+SLIP))/risk)


def assess(bars, row, cached):
    from run_recent_blend import FAMILIES, candidate
    hold, mode = int(row["max_hold_sessions"]), row["strategy"]
    weights = {g:1/len(FAMILIES) for g in FAMILIES}
    past, forward = [], []
    blocked_until = -1
    for i in range(20,len(bars)-hold):
        if i < blocked_until:
            continue
        signal = candidate(cached[i],mode,weights,False)
        if signal is None:
            continue
        outcome = trial(bars,i,signal["stop"],hold)
        if outcome is None:
            continue
        old = propose(bars.iloc[:i+1],outcome["entry"],signal["stop"],past)
        if old["assessed_target"] is not None and old["assessed_net_rr"] >= MIN_NET_RR:
            forward.append(trial(bars,i,signal["stop"],hold,old["assessed_target"]))
        past.append(dict(signal_date=str(bars.index[i].date()), end_date=str(bars.index[i+hold].date()), **outcome))
        blocked_until = i+hold
    result = propose(bars,float(row["provisional_entry"]),float(row["stop"]),past)
    count = len(forward)
    mean_r = float(np.mean([p["net_r"] for p in forward])) if count else None
    result.update(walkforward_examples=count, walkforward_mean_net_r=mean_r,
        walkforward_target_hit_pct=float(100*np.mean([p["target_hit"] for p in forward])) if count else None)
    if len(past) < MIN_TRAIN:
        status = "INSUFFICIENT_HISTORY"
    elif result["assessed_target"] is None:
        status = "SKIP_NO_SUPPORTED_UPSIDE"
    elif result["assessed_net_rr"] < MIN_NET_RR:
        status = "SKIP_LOW_NET_RR"
    elif count < MIN_FORWARD:
        status = "INSUFFICIENT_WALKFORWARD"
    elif mean_r <= 0:
        status = "SKIP_NONPOSITIVE_WALKFORWARD"
    else:
        status = "EXPERIMENTAL_CANDIDATE"
    result["target_status"] = status
    return result, dict(completed_nonoverlapping_examples=past, walkforward_results=forward)


def upgrade(output="reports/latest_setups"):
    import yfinance as yf
    import exchange_calendars as xcals
    from run_recent_blend import features, prepare
    out = Path(output)
    report = json.loads((out/"setups.json").read_text(encoding="utf-8"))
    if report.get("status") != "ok":
        raise ValueError("Unsuccessful base scan")
    for name in ("setups.json","setups.csv","summary.md"):
        (out/("baseline_2r_"+name)).write_bytes((out/name).read_bytes())
    cache, audits = {}, {}
    cutoff = pd.Timestamp(report["signal_date"])+pd.Timedelta(days=1)
    for row in report["setups"]:
        ticker = row["ticker"]
        row["reference_2r_target"] = row["provisional_target"]
        row["baseline_rank"] = row["provisional_rank"]
        try:
            if ticker not in cache:
                raw = yf.Ticker(ticker).history(start=str((cutoff-pd.DateOffset(years=5)).date()),
                    end=str(cutoff.date()),interval="1d",auto_adjust=True,actions=False,raise_errors=True)
                bars = prepare(raw,cutoff)
                calendar = xcals.get_calendar(report["calendar"])
                sessions = pd.DatetimeIndex(calendar.sessions_in_range(bars.index[0],bars.index[-1])).tz_localize(None).normalize()
                if not bars.index.equals(sessions):
                    raise ValueError("Missing historical exchange sessions")
                snapshot = pd.read_csv(out/f"bars_{ticker}.csv",index_col="Date",parse_dates=True)
                if not bars.index[-20:].equals(snapshot.index[-20:]) or not np.allclose(
                    bars[["Open","High","Low","Close"]].iloc[-20:],
                    snapshot[["Open","High","Low","Close"]].iloc[-20:],rtol=1e-7,atol=1e-7):
                    raise ValueError("Five-year data differs from the base-scan snapshot")
                bars.to_csv(out/f"target_history_{ticker}.csv",index_label="Date")
                cache[ticker] = (bars,features(bars))
            bars,cached = cache[ticker]
            check,audit = assess(bars,row,cached)
            audits[f"{ticker}_{row['strategy']}_h{row['max_hold_sessions']}"] = audit
        except Exception as exc:
            check = dict(target_status="TARGET_DATA_ERROR",assessed_target=None,assessed_net_rr=None,
                         target_error=f"{type(exc).__name__}: {exc}")
        row.update(check)
        row["provisional_target"] = row["assessed_target"]
        row["planned_target_profit"] = (row["shares"]*(row["assessed_target"]*(1-SLIP)-
            row["provisional_entry"]*(1+SLIP))) if row["assessed_target"] is not None else None
        row["eligible_at_reference_price"] = row["shares"] > 0 and row["target_status"] == "EXPERIMENTAL_CANDIDATE"
        row["upside_scenario"] = (f"Experimental assessed TP: {row['assessed_target']}; net RR: {row['assessed_net_rr']}. "
            f"Status: {row['target_status']}. No target guarantee; recalculation required at actual entry.")
        row["probability_note"] = "Walk-forward hit rate is historical, not a calibrated forecast. No guarantee or live-trading validation."
        row["ranking_explanation"] = "Original strategy ordering, filtered by target assessment and affordability; not ranked by predicted profit."
        row["provisional_rank"] = None
    for mode in ("compression_family","balanced_blend"):
        for hold in (5,7):
            group = sorted([r for r in report["setups"] if r["strategy"] == mode and r["max_hold_sessions"] == hold
                and r["eligible_at_reference_price"]],key=lambda r:r["baseline_rank"] or 10**9)
            for rank,row in enumerate(group,1):
                row["provisional_rank"] = rank
    notes = ("EXPERIMENTAL RESEARCH ONLY. Stops and share sizing unchanged; no orders. "
        "Target cap is median stop-truncated favorable excursion in raw R from at least 20 prior, nonoverlapping "
        "same-ticker/same-strategy setups over up to five years, separately for each holding period. "
        "Cap at the nearest confirmed 5-bar swing high from the last 60 sessions, less 0.1 ATR(14); no such high "
        "does not imply unlimited upside. ATR is a simple 14-session mean of true range, not a forecast. "
        "Historical walk-forward targets use only earlier completed examples and then-known confirmed highs. "
        "Filters require net RR >= 1.25, at least 10 qualifying walk-forward examples and positive mean net R. "
        "These are disclosed conservative engineering heuristics, NOT optimized or independently validated thresholds. "
        "15 bps/side; stop-first on ambiguous daily bars; ignore unknown stop-day highs when measuring excursion. "
        "Historical results are per-unit signal diagnostics, not a portfolio backtest; commissions, news and earnings "
        "are not modeled. Current-universe bias and retrospective adjusted data limit evidence. "
        "Insufficient evidence is not a buy. Both scan equity and prices use the selected market currency. "
        "All targets are provisional at signal close; rerun the assessment at actual entry. Original 2R reports are retained as baseline files.")
    report["target_method"] = notes
    (out/"target_audit.json").write_text(json.dumps(audits,indent=2,allow_nan=False),encoding="utf-8")
    (out/"setups.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    if report["setups"]:
        pd.DataFrame(report["setups"]).to_csv(out/"setups.csv",index=False)
    text = f"# Data-checked {report['market'].upper()} targets ({report['currency']})\n\n{notes}\n\n"
    text += "| Ticker | Strategy | Hold | Status | Ref entry | SL | 2R benchmark | Assessed TP | Net RR | Past examples | Walk-forward N | Walk-forward mean R |\n"
    text += "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    fmt = lambda v: "N/A" if v is None else f"{float(v):.2f}"
    for r in report["setups"]:
        text += (f"| {r['ticker']} | {r['strategy']} | {r['max_hold_sessions']} | {r['target_status']} "
            f"| {fmt(r['provisional_entry'])} | {fmt(r['stop'])} | {fmt(r['reference_2r_target'])} "
            f"| {fmt(r['assessed_target'])} | {fmt(r['assessed_net_rr'])} | {r.get('historical_examples','N/A')} "
            f"| {r.get('walkforward_examples','N/A')} | {fmt(r.get('walkforward_mean_net_r'))} |\n")
        if r.get("target_error"):
            text += f"\nData diagnostic for {r['ticker']}: {r['target_error']}\n\n"
    if not report["setups"]:
        text += "\nNo qualifying base setups; no target assessment invented.\n"
    for r in report["setups"]:
        text += f"\n## {r['ticker']} / {r['strategy']} / {r['max_hold_sessions']} sessions\n\n"
        for key in ("why_rules","price_evidence","ranking_explanation","upside_scenario","downside_scenario","time_exit_scenario"):
            text += f"- {key.replace('_',' ').capitalize()}: {r[key]}\n"
        text += f"- Conditional entry: {r['conditional_entry_date']}; latest exit: {r['latest_exit_date']}; shares: {r['shares']}; experimental eligible: {r['eligible_at_reference_price']}.\n"
    (out/"summary.md").write_text(text,encoding="utf-8")
    print(text)


if __name__ == "__main__":
    runpy.run_module("explain_scan",run_name="__main__")
    upgrade()
