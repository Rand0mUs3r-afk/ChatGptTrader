"""Recent-weighted swing research. No orders. Five/seven-session limits; daily bars are not scalping data."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

CORE = ("breakout3", "momentum3", "reversal2", "dip_rebound3", "inside_breakout", "failed_reclaim", "compression_breakout")
FAST = ("fast_breakout", "fast_reversal", "fast_momentum", "bullish_engulfing", "close_strength")
FAMILIES = {
    "trend": {"breakout3", "momentum3", "fast_breakout", "fast_momentum"},
    "recovery": {"reversal2", "dip_rebound3", "failed_reclaim", "fast_reversal", "bullish_engulfing"},
    "compression": {"inside_breakout", "compression_breakout"}}
MODES = CORE + FAST + ("momentum_union", "two_vote_blend", "reversal_no_chase", "market_gated_union") + tuple(x+"_family" for x in FAMILIES) + ("balanced_blend", "recent_blend", "cash")


def prepare(raw, cutoff):
    frame = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    if frame.index.has_duplicates:
        raise ValueError("Duplicate sessions")
    cutoff = pd.Timestamp(cutoff).tz_localize(None).normalize()
    frame = frame.sort_index().loc[lambda x: (x.index < cutoff) & (x.index >= cutoff-pd.DateOffset(years=5))]
    frame = frame.apply(pd.to_numeric, errors="raise")
    if frame.empty or not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Empty or nonfinite data")
    if ((frame[["Open","High","Low","Close"]] <= 0).any().any() or (frame.Volume < 0).any()
            or (frame.Low > frame[["Open","Close"]].min(axis=1)).any()
            or (frame.High < frame[["Open","Close"]].max(axis=1)).any()):
        raise ValueError("Invalid OHLCV")
    return frame


def features(frame):
    o,h,l,c = (frame[x] for x in ("Open","High","Low","Close"))
    span, bull = h-l, c>o
    high3, low3 = h.shift().rolling(3).max(), l.shift().rolling(3).min()
    mean, std = c.shift().rolling(3).mean(), c.shift().rolling(3).std(ddof=0)
    checks = {
        "breakout3": bull & (c>high3),
        "momentum3": bull & (c>c.shift()) & (c.shift()>c.shift(2)),
        "reversal2": bull & (c.shift()<o.shift()) & (c>h.shift()),
        "dip_rebound3": bull & (std>0) & (c.shift()<mean-std) & (c>c.shift()),
        "inside_breakout": bull & (h.shift()<h.shift(2)) & (l.shift()>l.shift(2)) & (c>h.shift()),
        "failed_reclaim": bull & (span>0) & (l<low3) & (c>low3) & ((c-l)>=0.75*span),
        "compression_breakout": bull & (span.shift()<span.shift(2)) & (span.shift()<span.shift(3)) & (c>h.shift()),
        "fast_breakout": bull & (c>h.shift()),
        "fast_reversal": bull & (c.shift()<o.shift()) & (c>h.shift()),
        "fast_momentum": bull & (c>c.shift()),
        "bullish_engulfing": bull & (c.shift()<o.shift()) & (o<=c.shift()) & (c>=o.shift()),
        "close_strength": bull & (span>0) & ((c-l)>=0.75*span)}
    base_stop = l.rolling(3).min()-0.1*span.rolling(3).mean()
    result = []
    for i in range(len(frame)):
        active = {name for name, check in checks.items() if i>=3 and bool(check.iloc[i])}
        stops = {name: float(base_stop.iloc[i]) for name in active}
        if "failed_reclaim" in stops:
            stops["failed_reclaim"] = float(l.iloc[i]-0.1*span.iloc[i])
        if "compression_breakout" in stops:
            stops["compression_breakout"] = float(l.iloc[i-1]-0.1*span.iloc[i-1])
        active = {name for name in active if math.isfinite(stops[name]) and 0<stops[name]<c.iloc[i]}
        groups = tuple(name for name,members in FAMILIES.items() if active & members)
        result.append(dict(active=active, stops=stops, groups=groups, close=float(c.iloc[i]), span=float(span.iloc[i]),
            quality=float((c.iloc[i]-l.iloc[i])/span.iloc[i]) if span.iloc[i]>0 else 0.0))
    return result


def monthly_weights(ledgers, boundary, half_life=126):
    scores, audit = {}, {}
    for family in FAMILIES:
        closed = [r for r in ledgers.get(family,[]) if r["exit_index"] < boundary]
        if closed:
            decay = np.array([0.5**((boundary-r["exit_index"])/half_life) for r in closed])
            returns = np.array([r["risk_multiple"] for r in closed])
            effective = float(decay.sum()**2/(decay@decay))
            mean = float(decay@returns/decay.sum())
            shrunk = mean*effective/(effective+20)
        else:
            effective, shrunk = 0.0, 0.0
        scores[family] = math.exp(float(np.clip(shrunk,-1,1)))
        audit[family] = dict(closed_trades=len(closed), effective_trades=effective,
            last_exit_index=max((r["exit_index"] for r in closed),default=None))
    total = sum(scores.values())
    weights = {name: 0.25/len(FAMILIES)+0.75*scores[name]/total for name in FAMILIES}
    return weights, audit


def candidate(feature, mode, weights, market_up):
    active, groups = feature["active"], feature["groups"]
    if mode == "cash":
        return None
    if mode in CORE+FAST:
        votes = {mode} & active
    elif mode.endswith("_family"):
        votes = active & FAMILIES[mode[:-7]]
    elif mode in ("balanced_blend","recent_blend"):
        if len(groups)<2:
            return None
        votes = set().union(*(active & FAMILIES[g] for g in groups))
    elif mode == "momentum_union":
        votes = active & {"breakout3","momentum3"}
    elif mode == "two_vote_blend":
        votes = active & set(CORE[:5])
        if len(votes)<2:
            return None
    elif mode == "reversal_no_chase":
        votes = active & {"reversal2"}
    else:
        if not market_up:
            return None
        votes = active & {"reversal2","compression_breakout"}
    if not votes:
        return None
    score = sum(weights[g] for g in groups) if mode in ("balanced_blend","recent_blend") else 1.0
    return dict(stop=min(feature["stops"][v] for v in votes), score=score,
        groups=tuple(g for g in groups if FAMILIES[g] & votes), votes=sorted(votes),
        max_open=feature["close"]+0.5*feature["span"] if mode=="reversal_no_chase" else None)


def simulate(data, cached, mode, hold, bps, start_index=252, ledgers=None):
    if mode not in MODES or hold not in (5,7) or bps not in (5,15):
        raise ValueError("Invalid trial")
    dates = data["SPY"].index
    if not 4<=start_index<len(dates) or any(not f.index.equals(dates) for f in data.values()):
        raise ValueError("Invalid aligned history or evaluation boundary")
    arrays = {t: f[["Open","High","Low","Close"]].to_numpy(dtype=float) for t,f in data.items()}
    equity, position, last_exit, trades, curve, updates = 1000.0, None, -1, [], [], []
    slip, month = bps/10000.0, None
    weights = {g:1/len(FAMILIES) for g in FAMILIES}
    skips = dict(unaffordable=0, risk_size=0, invalid_open=0, no_chase=0)
    for i in range(start_index,len(dates)):
        key = str(dates[i].to_period("M"))
        if mode=="recent_blend" and key!=month:
            boundary = int(dates.searchsorted(pd.Timestamp(key+"-01")))
            weights, audit = monthly_weights(ledgers or {},boundary)
            updates.append(dict(effective_date=str(dates[i].date()), boundary=boundary, weights=weights.copy(), audit=audit))
            month = key
        if position is None and i>last_exit and equity>0:
            market_up = i>=4 and arrays["SPY"][i-1,3]>arrays["SPY"][i-4,3]
            candidates = []
            for ticker in sorted(data):
                f = cached[ticker][i-1]
                signal = candidate(f,mode,weights,market_up)
                if signal:
                    candidates.append((-signal["score"],-f["quality"] if mode in ("balanced_blend","recent_blend") else 0,ticker,signal))
            for _,_,ticker,signal in sorted(candidates,key=lambda x:x[:3]):
                entry = arrays[ticker][i,0]
                if entry<=signal["stop"]:
                    skips["invalid_open"]+=1
                    continue
                if signal["max_open"] is not None and entry>signal["max_open"]:
                    skips["no_chase"]+=1
                    continue
                fill, stop = entry*(1+slip),signal["stop"]
                unit_risk = fill-stop*(1-slip)
                affordable = math.floor(equity*0.25/fill)
                if affordable<1:
                    skips["unaffordable"]+=1
                    continue
                shares = min(affordable,math.floor(equity*0.25*0.06/unit_risk))
                if shares<1:
                    skips["risk_size"]+=1
                    continue
                position = dict(ticker=ticker,entry_index=i,signal_date=str(dates[i-1].date()),
                    entry_date=str(dates[i].date()),entry_fill=float(fill),stop=float(stop),target=float(entry+2*(entry-stop)),
                    shares=shares,equity_before=equity,position_cost=shares*fill,risk_budget=equity*0.015,
                    planned_stop_risk=shares*unit_risk,families=signal["groups"],votes=signal["votes"],weights=weights.copy())
                break
        if position is not None:
            p = position
            o,h,l,c = arrays[p["ticker"]][i]
            age = i-p["entry_index"]+1
            price, reason = None,None
            if o<=p["stop"]:
                price,reason=o,"gap_stop"
            elif o>=p["target"]:
                price,reason=p["target"],"target_gap"
            elif l<=p["stop"]:
                price,reason=p["stop"],"stop"
            elif h>=p["target"]:
                price,reason=p["target"],"target"
            elif age>=hold:
                price,reason=c,"time_exit"
            elif i==len(dates)-1:
                price,reason=c,"window_end"
            if price is not None:
                pnl = p["shares"]*(price*(1-slip)-p["entry_fill"])
                equity+=pnl
                trades.append(dict(**p,exit_index=i,exit_date=str(dates[i].date()),exit_fill=float(price*(1-slip)),
                    exit_reason=reason,net_pnl=float(pnl),risk_multiple=float(pnl/p["planned_stop_risk"]),equity_after=equity,
                    held_sessions=age,held_calendar_days=int((dates[i]-dates[p["entry_index"]]).days)))
                position,last_exit=None,i
        mtm = equity if position is None else equity+position["shares"]*(arrays[position["ticker"]][i,3]*(1-slip)-position["entry_fill"])
        curve.append(dict(date=str(dates[i].date()),equity=float(mtm)))
    values = np.array([1000.0]+[x["equity"] for x in curve])
    peak = np.maximum.accumulate(values)
    pnl = np.array([x["net_pnl"] for x in trades])
    losing, longest = 0,0
    for value in pnl:
        losing=losing+1 if value<0 else 0
        longest=max(longest,losing)
    forced = [r for r in trades if r["exit_reason"]=="window_end"]
    summary = dict(strategy=mode,hold=hold,bps_per_side=bps,starting_equity=1000.0,final_equity=equity,
        net_pnl=float(pnl.sum()),return_pct=(equity/1000-1)*100,trades=len(trades),wins=int((pnl>0).sum()),
        losses=int((pnl<0).sum()),breakeven=int((pnl==0).sum()),win_rate_pct=float((pnl>0).mean()*100) if len(pnl) else None,
        profit_factor=float(pnl[pnl>0].sum()/-pnl[pnl<0].sum()) if (pnl<0).any() else None,
        max_consecutive_losses=longest,daily_mtm_drawdown_pct=float(((peak-values)/peak).max()*100),
        average_held_sessions=float(np.mean([r["held_sessions"] for r in trades])) if trades else None,
        shortest_hold_sessions=min((r["held_sessions"] for r in trades),default=None),
        longest_hold_sessions=max((r["held_sessions"] for r in trades),default=None),
        window_end_exits=len(forced),window_end_pnl=sum(r["net_pnl"] for r in forced),skip_counts=skips)
    return trades,curve,summary,updates


def main():
    import yfinance as yf
    from swingbot.scanner import load_tickers
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asof",default=str(pd.Timestamp.now(tz="America/New_York").date()),help="Exclusive cutoff")
    parser.add_argument("--output",default="reports/recent_swing_blend")
    args=parser.parse_args()
    cutoff=pd.Timestamp(args.asof).tz_localize(None).normalize()
    if cutoff>pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize():
        raise ValueError("Future cutoff prohibited")
    tickers=sorted(set(load_tickers("config/tickers.txt")) | {"SPY"})
    data={}
    for ticker in tickers:
        raw=yf.Ticker(ticker).history(start=str((cutoff-pd.DateOffset(years=5)).date()),end=str(cutoff.date()),interval="1d",auto_adjust=True,actions=False,raise_errors=True)
        data[ticker]=prepare(raw,cutoff)
    dates=data["SPY"].index
    if len(dates)<300 or any(not f.index.equals(dates) for f in data.values()):
        raise ValueError("At least 300 identical sessions required; no silently dropped tickers/dates")
    cached={t:features(f) for t,f in data.items()}
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    coverage={}
    for n,(ticker,frame) in enumerate(sorted(data.items())):
        snapshot=frame.to_csv(index_label="Date")
        filename=f"bars_{n:04d}.csv"
        (output/filename).write_text(snapshot,encoding="utf-8")
        coverage[ticker]=dict(file=filename,bars=len(frame),sha256=hashlib.sha256(snapshot.encode()).hexdigest())
    results=[]
    for hold in (5,7):
        for bps in (15,5):
            ledgers={g:simulate(data,cached,g+"_family",hold,bps,start_index=4)[0] for g in FAMILIES}
            (output/f"training_shadows_h{hold}_bps{bps}.json").write_text(json.dumps(ledgers,indent=2,allow_nan=False),encoding="utf-8")
            for mode in MODES:
                trades,curve,summary,weights=simulate(data,cached,mode,hold,bps,start_index=252,ledgers=ledgers)
                trial=f"{mode}_h{hold}_bps{bps}"
                (output/f"{trial}_journal.json").write_text(json.dumps(trades,indent=2,allow_nan=False),encoding="utf-8")
                pd.DataFrame(trades).to_csv(output/f"{trial}_journal.csv",index=False)
                daily=pd.DataFrame(curve)
                daily.to_csv(output/f"{trial}_daily_equity.csv",index=False)
                monthly=daily.assign(month=pd.to_datetime(daily.date).dt.to_period("M").astype(str)).groupby("month").equity.last()
                pd.DataFrame(dict(final_equity=monthly,return_pct=(monthly/monthly.shift(fill_value=1000)-1)*100)).to_csv(output/f"{trial}_monthly.csv")
                contributions=[dict(family=g,attributed_net_pnl=sum(r["net_pnl"]/len(r["families"]) for r in trades if g in r["families"])) for g in FAMILIES]
                contributions.append(dict(family="unassigned_quality_only",attributed_net_pnl=sum(r["net_pnl"] for r in trades if not r["families"])))
                pd.DataFrame(contributions).to_csv(output/f"{trial}_family_contributions.csv",index=False)
                if weights:
                    (output/f"{trial}_weights.json").write_text(json.dumps(weights,indent=2,allow_nan=False),encoding="utf-8")
                results.append(summary)
    table=pd.DataFrame(results).sort_values(["bps_per_side","hold","net_pnl"],ascending=[False,True,False])
    table.to_csv(output/"all_trials.csv",index=False)
    manifest=dict(experiment="recent_weighted_swing_blend",cutoff_exclusive=str(cutoff.date()),history_start=str(dates[0].date()),
        evaluation_start=str(dates[252].date()),history_end=str(dates[-1].date()),training_sessions=252,coverage=coverage,
        account=dict(starting_equity=1000,allocation_pct=25,risk_pct_of_allocation=6,initial_risk_budget=15),
        trials=len(results),scalping="DISABLED: daily bars; intraday coverage and execution model not verified",results=results)
    (output/"results.json").write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding="utf-8")
    text="# Recent-weighted swing blend — five/seven-session maximum\n\n"
    text+=f"History: {manifest['history_start']} to {manifest['history_end']}. Evaluation starts {manifest['evaluation_start']} after 252 training sessions. Monthly weights use only shadow trades closed before each calendar month.\n\n"
    text+="Each row is a separate $1,000 account. Allocation cap 25%; initial planned-risk ceiling $15. Costs change sizing and trade paths. Daily MTM includes estimated liquidation slippage. Current-universe bias, development-data reuse, daily stop-first fills, zero commission/cash interest, and forced end exits limit conclusions. Scalping disabled.\n\n"
    text+="| Strategy | Max hold | bps/side | Trades | Won | Lost | Breakeven | Final equity | Net P&L | Win % | Avg sessions | Min/max | MTM drawdown % | Forced exits |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|\n"
    for r in table.to_dict("records"):
        rate="N/A" if pd.isna(r["win_rate_pct"]) else f"{r['win_rate_pct']:.1f}"
        avg="N/A" if pd.isna(r["average_held_sessions"]) else f"{r['average_held_sessions']:.2f}"
        bounds="N/A" if r["trades"]==0 else f"{int(r['shortest_hold_sessions'])}/{int(r['longest_hold_sessions'])}"
        text+=f"| {r['strategy']} | {r['hold']} | {r['bps_per_side']} | {r['trades']} | {r['wins']} | {r['losses']} | {r['breakeven']} | ${r['final_equity']:.2f} | {r['net_pnl']:+.2f} | {rate} | {avg} | {bounds} | {r['daily_mtm_drawdown_pct']:.2f} | {r['window_end_exits']} |\n"
    (output/"summary.md").write_text(text,encoding="utf-8")
    print(text)


if __name__=="__main__":
    main()
