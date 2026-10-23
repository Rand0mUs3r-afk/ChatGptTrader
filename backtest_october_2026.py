"""October 2026 entry-only backtest of the experimental joint SL/TP rules. No orders."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

START, END = pd.Timestamp("2026-10-01"), pd.Timestamp("2026-11-01")
MODES = ("compression_family","balanced_blend")


def simulate(data, cached, mode, hold, equity=1000.0, assessor=None):
    from run_recent_blend import candidate, FAMILIES
    from scan_latest_setups import price_plan
    if assessor is None:
        from assess_targets import assess
        assessor = assess
    dates = next(iter(data.values())).index
    if any(not f.index.equals(dates) for f in data.values()):
        raise ValueError("Unaligned exchange sessions")
    weights = {g:1/len(FAMILIES) for g in FAMILIES}
    initial, position, journal, daily, decisions = float(equity), None, [], [], []
    slip = 0.0015
    for i,date in enumerate(dates):
        if not START <= date < END:
            continue
        if i < 20:
            raise ValueError("Insufficient pre-October warm-up")
        if position is None and equity > 0:
            candidates = []
            for ticker in sorted(data):
                feature = cached[ticker][i-1]
                signal = candidate(feature,mode,weights,False)
                if signal:
                    candidates.append((-signal["score"],-feature["quality"] if mode == "balanced_blend" else 0,ticker,signal))
            for _,_,ticker,signal in sorted(candidates,key=lambda x:x[:3]):
                entry,stop = float(data[ticker].Open.iloc[i]),float(signal["stop"])
                decision = dict(entry_date=str(date.date()),ticker=ticker)
                if entry <= stop:
                    decisions.append(dict(**decision,status="SKIP_OPEN_AT_OR_BELOW_STOP"))
                    continue
                plan = price_plan(entry,stop,equity)
                if plan["shares"] < 1:
                    decisions.append(dict(**decision,status="SKIP_UNAFFORDABLE"))
                    continue
                row = dict(strategy=mode,max_hold_sessions=hold,provisional_entry=entry,stop=stop)
                check,_ = assessor(data[ticker].iloc[:i],row,cached[ticker][:i])
                decisions.append(dict(**decision,status=check["target_status"],net_rr=check.get("assessed_net_rr")))
                if check["target_status"] != "EXPERIMENTAL_CANDIDATE":
                    continue
                fill = entry*(1+slip)
                position = dict(ticker=ticker,signal_date=str(dates[i-1].date()),entry_date=str(date.date()),
                    entry_index=i,entry_open=entry,entry_fill=fill,stop=stop,target=float(check["assessed_target"]),
                    shares=int(plan["shares"]),planned_stop_risk=float(plan["planned_stop_risk"]),
                    position_cost=float(plan["estimated_cost"]),net_rr=float(check["assessed_net_rr"]),
                    historical_examples=check["historical_examples"],walkforward_examples=check["walkforward_examples"],
                    votes=", ".join(signal["votes"]),families=", ".join(signal["groups"]),
                    closed=False,exit_date=None,exit_fill=None,exit_reason=None,net_pnl=None)
                journal.append(position)
                break
        if position is not None:
            p = position
            bar = data[p["ticker"]].iloc[i]
            o,h,l,c = (float(bar[k]) for k in ("Open","High","Low","Close"))
            price,reason = None,None
            if o <= p["stop"]:
                price,reason = o,"gap_stop"
            elif o >= p["target"]:
                price,reason = p["target"],"target_gap"
            elif l <= p["stop"]:
                price,reason = p["stop"],"stop"
            elif h >= p["target"]:
                price,reason = p["target"],"target"
            elif i-p["entry_index"]+1 >= hold:
                price,reason = c,"time_exit"
            if price is not None:
                pnl = p["shares"]*(price*(1-slip)-p["entry_fill"])
                equity += pnl
                p.update(closed=True,exit_date=str(date.date()),exit_fill=float(price*(1-slip)),
                    exit_reason=reason,net_pnl=float(pnl),held_sessions=i-p["entry_index"]+1)
                position = None
        unrealized = 0.0 if position is None else position["shares"]*(float(data[position["ticker"]].Close.iloc[i])*(1-slip)-position["entry_fill"])
        daily.append(dict(date=str(date.date()),realized_equity=float(equity),
            unrealized_estimated_liquidation_pnl=float(unrealized),marked_equity=float(equity+unrealized)))
    if not daily:
        raise ValueError("No completed October sessions available")
    if position is not None:
        position.update(exit_reason="OPEN_AT_CUTOFF",mark_date=daily[-1]["date"],
            unrealized_estimated_liquidation_pnl=daily[-1]["unrealized_estimated_liquidation_pnl"],
            held_sessions=int(dates.get_loc(pd.Timestamp(daily[-1]["date"])))-position["entry_index"]+1)
    closed = [r for r in journal if r["closed"]]
    profits = [r["net_pnl"] for r in closed]
    curve = np.array([initial]+[r["marked_equity"] for r in daily])
    peaks = np.maximum.accumulate(curve)
    summary = dict(strategy=mode,max_hold_sessions=hold,starting_equity=initial,
        entries=len(journal),closed_trades=len(closed),wins=sum(p>0 for p in profits),
        losses=sum(p<0 for p in profits),breakeven=sum(p==0 for p in profits),
        open_positions=int(position is not None),realized_net_pnl=float(equity-initial),
        unrealized_estimated_liquidation_pnl=daily[-1]["unrealized_estimated_liquidation_pnl"],
        ending_marked_equity=daily[-1]["marked_equity"],
        total_return_pct=float((curve[-1]/initial-1)*100),
        win_rate_closed_pct=float(100*sum(p>0 for p in profits)/len(profits)) if profits else None,
        max_marked_drawdown_pct=float(np.max((peaks-curve)/peaks)*100),
        asof=daily[-1]["date"])
    return summary,journal,daily,decisions


def main():
    import exchange_calendars as xcals
    from checked_history import fetch_daily, PRICE_BASIS
    from swingbot.scanner import load_tickers
    from assess_structural_risk import risk_features
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market",choices=("us","tsx","both"),default="both")
    parser.add_argument("--equity-us",type=float,default=1000.0)
    parser.add_argument("--equity-tsx",type=float,default=1000.0)
    args = parser.parse_args()
    if any(not math.isfinite(x) or x<=0 for x in (args.equity_us,args.equity_tsx)):
        raise ValueError("Positive finite scenario equity required")
    out = Path("reports/october_2026")
    out.mkdir(parents=True,exist_ok=True)
    now,results,coverage = pd.Timestamp.now(tz="UTC"),[],{}
    for market in (("us","tsx") if args.market == "both" else (args.market,)):
        calendar = xcals.get_calendar("XNYS" if market == "us" else "XTSE")
        sessions = calendar.sessions_in_range(START-pd.DateOffset(years=5),END-pd.Timedelta(days=1))
        complete = [s for s in sessions if calendar.session_close(s)+pd.Timedelta(minutes=20)<=now]
        if not complete or pd.Timestamp(complete[-1]).tz_localize(None)<START:
            raise ValueError("October 2026 has no completed available sessions")
        cutoff = pd.Timestamp(complete[-1]).tz_localize(None).normalize()+pd.Timedelta(days=1)
        required = pd.DatetimeIndex(complete[-20:]).tz_localize(None).normalize()
        tickers = sorted(set(load_tickers("config/tickers.txt" if market == "us" else "config/tickers_tsx.txt")))
        if not tickers:
            raise ValueError("Empty watchlist")
        directory = out/market
        directory.mkdir(exist_ok=True)
        data = {}
        for ticker in tickers:
            frame = fetch_daily(ticker,START-pd.DateOffset(years=5),cutoff,required)
            expected = pd.DatetimeIndex(calendar.sessions_in_range(frame.index[0],frame.index[-1])).tz_localize(None).normalize()
            if not frame.index.equals(expected):
                raise ValueError(f"{ticker}: historical session gaps")
            if sum(frame.index<START)<300:
                raise ValueError(f"{ticker}: insufficient pre-October history")
            data[ticker] = frame
            snapshot = frame.to_csv(index_label="Date")
            (directory/f"bars_{ticker}.csv").write_text(snapshot,encoding="utf-8")
            coverage[f"{market}:{ticker}"] = dict(first=str(frame.index[0].date()),last=str(frame.index[-1].date()),
                bars=len(frame),sha256=hashlib.sha256(snapshot.encode()).hexdigest())
        for mode in MODES:
            cached = {ticker:risk_features(frame,mode) for ticker,frame in data.items()}
            for hold in (5,7):
                summary,journal,daily,decisions = simulate(data,cached,mode,hold,
                    equity=args.equity_us if market == "us" else args.equity_tsx)
                summary.update(market=market,currency="USD" if market == "us" else "CAD")
                results.append(summary)
                trial=f"{mode}_h{hold}"
                (directory/f"{trial}_journal.json").write_text(json.dumps(journal,indent=2,allow_nan=False),encoding="utf-8")
                pd.DataFrame(journal,columns=list(journal[0]) if journal else ["ticker","entry_date","exit_date","closed","net_pnl"]).to_csv(directory/f"{trial}_journal.csv",index=False)
                pd.DataFrame(daily).to_csv(directory/f"{trial}_daily_equity.csv",index=False)
                pd.DataFrame(decisions,columns=["entry_date","ticker","status","net_rr"]).to_csv(directory/f"{trial}_decisions.csv",index=False)
    notes = ("Only entries dated October 1-31, 2026 are eligible; evaluation ends at the latest completed October "
        "session available at run time. Earlier bars are training/warm-up only. Each market/strategy/holding period "
        "is an independent flat-start account; one position at a time, no same-day reentry after exit, no FX pooling. "
        "Signals/stops use previous close; entry is next session open. Target and net RR are recalculated at that open "
        "using only earlier bars and matured historical examples. Current structural SL, historical TP and walk-forward "
        "filters apply. 25% allocation and 1.5% equity planned-risk caps; 15 bps/side; zero commissions/dividend cash. "
        "Stop-first on ambiguous daily bars; gap-stop losses can exceed plan. Positions still open at cutoff are NOT "
        "forced wins/losses: closed P&L and estimated-liquidation unrealized P&L are separate. No future October data "
        "is fabricated. This is a development-sample research backtest, with current-universe/survivorship bias, "
        "retrospective Yahoo data, and no independent live validation; not a guaranteed forecast.")
    manifest = dict(generated_at=str(now),entry_start="2026-10-01",entry_end_exclusive="2026-11-01",
        price_basis=PRICE_BASIS,notes=notes,coverage=coverage,results=results)
    (out/"results.json").write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding="utf-8")
    pd.DataFrame(results).to_csv(out/"results.csv",index=False)
    text = f"# October 2026 entry-only backtest\n\n{notes}\n\n"
    text += "| Market | Strategy | Hold | As of | Entries | Closed | Won | Lost | Open | Realized P&L | Unrealized P&L | Marked equity | Return % | Drawdown % |\n"
    text += "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for r in results:
        text += (f"| {r['market']} ({r['currency']}) | {r['strategy']} | {r['max_hold_sessions']} | {r['asof']} "
            f"| {r['entries']} | {r['closed_trades']} | {r['wins']} | {r['losses']} | {r['open_positions']} "
            f"| {r['realized_net_pnl']:.2f} | {r['unrealized_estimated_liquidation_pnl']:.2f} "
            f"| {r['ending_marked_equity']:.2f} | {r['total_return_pct']:.2f} | {r['max_marked_drawdown_pct']:.2f} |\n")
    (out/"summary.md").write_text(text,encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
