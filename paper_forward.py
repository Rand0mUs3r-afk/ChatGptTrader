"""Prospective daily-bar paper simulator. No broker integration or real orders."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import numpy as np
import pandas as pd

MODELS = ("compression_family","balanced_blend")
RULES = dict(version="paper-forward-v1",currency="USD",initial_equity=1000.0,
    max_hold_sessions=7,allocation=0.25,risk=0.015,slippage=0.0015,target_r=2.0,quantity="whole")
COLS = ["Open","High","Low","Close","Volume"]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def clock(value=None):
    t = pd.Timestamp.now(tz="UTC") if value is None else pd.Timestamp(value)
    if t.tzinfo is None:
        raise ValueError("UTC-aware timestamp required")
    return t.tz_convert("UTC")


def label(value):
    return str(pd.Timestamp(value).tz_localize(None).date())


def latest_complete(calendar,now):
    day = now.tz_localize(None).normalize()
    sessions = calendar.sessions_in_range(day-pd.Timedelta(days=20),day)
    ready = [s for s in sessions if calendar.session_close(s)+pd.Timedelta(minutes=20)<=now]
    if not ready:
        raise ValueError("No completed session")
    return label(ready[-1])


def new_state(tickers,source_hash,now=None):
    tickers = sorted(set(tickers))
    if not tickers or {"AMD","AMZN"}&set(tickers):
        raise ValueError("Empty universe or excluded ticker")
    return dict(rules=RULES.copy(),source_hash=source_hash,tickers=tickers,created_at=str(clock(now)),
        last_session=None,pending=None,events=[],books={m:dict(equity=1000.0,position=None,trades=[],daily=[]) for m in MODELS})


def event(state,kind,data,now):
    row = dict(sequence=len(state["events"])+1,at=str(now),kind=kind,data=copy.deepcopy(data),
        previous_hash=state["events"][-1]["hash"] if state["events"] else None)
    row["hash"] = digest(row)
    state["events"].append(row)


def validate_bar(row):
    o,h,l,c,v = (float(row[k]) for k in COLS)
    if not all(math.isfinite(x) for x in (o,h,l,c,v)) or min(o,h,l,c)<=0 or v<0 or l>min(o,c) or h<max(o,c):
        raise ValueError("Invalid OHLCV; no price substitution")
    if float(row.get("Stock Splits",0))!=0:
        raise ValueError("Split requires manual corporate-action review; state unchanged")
    return o,h,l,c


def signals(bars,tickers):
    from run_recent_blend import features,candidate,FAMILIES
    weights = {g:1/len(FAMILIES) for g in FAMILIES}
    result = {m:[] for m in MODELS}
    for ticker in tickers:
        f = features(bars[ticker])[-1]
        for mode in MODELS:
            found = candidate(f,mode,weights,False)
            if found:
                result[mode].append(dict(ticker=ticker,stop=float(found["stop"]),score=float(found["score"]),
                    quality=float(f["quality"]),votes=list(found["votes"]),families=list(found["groups"])))
    for mode in MODELS:
        result[mode].sort(key=lambda r:(-r["score"],-r["quality"] if mode=="balanced_blend" else 0,r["ticker"]))
    return result


def make_plan(state,bars,calendar,now=None):
    now = clock(now)
    if state["pending"] is not None:
        return copy.deepcopy(state)
    signal_day = latest_complete(calendar,now)
    entry_day = label(calendar.next_session(pd.Timestamp(signal_day)))
    if now>=calendar.session_open(pd.Timestamp(entry_day)):
        raise ValueError("Too late for a prospective opening plan")
    if state["last_session"] not in (None,signal_day):
        raise ValueError("Settle missing sessions before planning")
    snapshots = {}
    for ticker in state["tickers"]:
        f = bars[ticker]
        expected = pd.DatetimeIndex(calendar.sessions_in_range(f.index[0],pd.Timestamp(signal_day))).tz_localize(None).normalize()
        if len(f)<20 or not f.index.equals(expected):
            raise ValueError(f"{ticker}: stale, future, duplicate or missing sessions")
        for row in f[COLS].to_dict("records"):
            validate_bar(row)
        if "Stock Splits" in f and (f["Stock Splits"].tail(4)!=0).any():
            raise ValueError("Recent split requires manual review")
        csv = f.to_csv(index_label="Date")
        snapshots[ticker] = dict(sha256=hashlib.sha256(csv.encode()).hexdigest(),csv=csv)
    ranked = signals(bars,state["tickers"])
    out = copy.deepcopy(state)
    for mode in MODELS:
        if out["books"][mode]["position"] is not None:
            ranked[mode] = []
    plan = dict(created_at=str(now),signal_date=signal_day,entry_date=entry_day,candidates=ranked,snapshots=snapshots,
        selection_status={m:"OCCUPIED" if out["books"][m]["position"] else "RANKED" if ranked[m] else "NO_SIGNAL" for m in MODELS})
    plan["hash"] = digest(plan)
    out["last_session"] = signal_day
    out["pending"] = plan
    event(out,"PREOPEN_PLAN",plan,now)
    return out


def settle(state,session,prices,calendar,now=None):
    now,session = clock(now),label(session)
    if state["last_session"] is None or session!=label(calendar.next_session(pd.Timestamp(state["last_session"]))):
        raise ValueError("Duplicate or out-of-order settlement")
    if now<calendar.session_close(pd.Timestamp(session))+pd.Timedelta(minutes=20):
        raise ValueError("Session not complete")
    for ticker in state["tickers"]:
        validate_bar(prices[ticker])
    plan = state["pending"]
    if plan is not None:
        unsigned = {k:v for k,v in plan.items() if k!="hash"}
        if digest(unsigned)!=plan["hash"] or plan["entry_date"]!=session or clock(plan["created_at"])>=calendar.session_open(pd.Timestamp(session)):
            raise ValueError("Invalid or late pre-open plan")
    out = copy.deepcopy(state)
    slip = RULES["slippage"]
    for mode in MODELS:
        book = out["books"][mode]
        if book["position"] is None:
            candidates = plan["candidates"][mode] if plan else []
            event(out,"ENTRY_CHECK",dict(model=mode,session=session,status="PREPLANNED" if plan else "NO_PREOPEN_PLAN_NO_ENTRY"),now)
            accepted = False
            for row in candidates:
                ticker,stop = row["ticker"],float(row["stop"])
                entry = float(prices[ticker]["Open"])
                if not math.isfinite(stop) or stop<=0:
                    raise ValueError("Invalid planned stop")
                status = "OPEN_AT_OR_BELOW_STOP" if entry<=stop else None
                fill,unit_risk = entry*(1+slip),entry*(1+slip)-stop*(1-slip)
                shares = 0 if status else min(math.floor(book["equity"]*.25/fill),math.floor(book["equity"]*.015/unit_risk))
                if not status and shares<1:
                    status = "WHOLE_SHARE_SIZING_REJECTED"
                event(out,"CANDIDATE",dict(model=mode,session=session,ticker=ticker,status=status or "PAPER_OPEN",shares=shares),now)
                if status:
                    continue
                book["position"] = dict(**row,signal_date=plan["signal_date"],entry_date=session,entry_open=entry,
                    entry_fill=fill,target=entry+2*(entry-stop),shares=shares,position_cost=shares*fill,
                    planned_stop_risk=shares*unit_risk,equity_before=book["equity"],plan_hash=plan["hash"])
                event(out,"PAPER_OPEN",dict(model=mode,position=book["position"]),now)
                accepted = True
                break
            if plan and not accepted:
                event(out,"NO_ENTRY",dict(model=mode,session=session),now)
        p = book["position"]
        unrealized = 0.0
        if p is not None:
            o,h,l,c = validate_bar(prices[p["ticker"]])
            age = len(calendar.sessions_in_range(pd.Timestamp(p["entry_date"]),pd.Timestamp(session)))
            price,reason = (o,"gap_stop") if o<=p["stop"] else (p["target"],"target_gap") if o>=p["target"] else (p["stop"],"stop") if l<=p["stop"] else (p["target"],"target") if h>=p["target"] else (c,"time_exit") if age>=7 else (None,None)
            if price is not None:
                pnl = p["shares"]*(price*(1-slip)-p["entry_fill"])
                book["equity"] += pnl
                trade = dict(**p,exit_date=session,exit_fill=price*(1-slip),exit_reason=reason,net_pnl=pnl,
                    realized_r=pnl/p["planned_stop_risk"],held_sessions=age)
                book["trades"].append(trade)
                book["position"] = None
                event(out,"PAPER_CLOSE",dict(model=mode,trade=trade),now)
            else:
                unrealized = p["shares"]*(c*(1-slip)-p["entry_fill"])
        daily = dict(session=session,realized_equity=book["equity"],unrealized_estimated_liquidation_pnl=unrealized,
            marked_equity=book["equity"]+unrealized)
        book["daily"].append(daily)
        event(out,"DAILY_MARK",dict(model=mode,**daily),now)
    out["last_session"],out["pending"] = session,None
    event(out,"SETTLED",dict(session=session,price_hash=digest(prices),prices=prices),now)
    return out


def summary(state):
    result = {}
    for mode,book in state["books"].items():
        pnls = [t["net_pnl"] for t in book["trades"]]
        positive,negative = [p for p in pnls if p>0],[-p for p in pnls if p<0]
        curve = np.array([1000.0]+[d["marked_equity"] for d in book["daily"]])
        result[mode] = dict(closed_trades=len(pnls),wins=len(positive),losses=len(negative),
            realized_net_pnl=sum(pnls),marked_equity=float(curve[-1]),open_positions=int(book["position"] is not None),
            average_net_pnl=sum(pnls)/len(pnls) if pnls else None,
            average_win=sum(positive)/len(positive) if positive else None,average_loss=sum(negative)/len(negative) if negative else None,
            profit_factor=sum(positive)/sum(negative) if negative else None,
            max_marked_drawdown_pct=float(100*np.max((np.maximum.accumulate(curve)-curve)/np.maximum.accumulate(curve))))
    return dict(paper_only=True,rules=state["rules"],last_session=state["last_session"],
        pending=state["pending"]["entry_date"] if state["pending"] else None,books=result)


def fetch_bars(tickers,day,calendar):
    import yfinance as yf
    from checked_history import fetch_daily
    start,end = pd.Timestamp(day)-pd.Timedelta(days=100),pd.Timestamp(day)+pd.Timedelta(days=1)
    required = pd.DatetimeIndex(calendar.sessions_in_range(start,pd.Timestamp(day))[-20:]).tz_localize(None).normalize()
    result = {}
    for ticker in tickers:
        actions = {}
        def get(recent_start=start):
            kwargs = dict(start=str(pd.Timestamp(recent_start).date()),end=str(end.date()),interval="1d",auto_adjust=False,actions=True)
            debug = getattr(getattr(yf,"config",None),"debug",None)
            if debug is not None and hasattr(debug,"hide_exceptions"):
                debug.hide_exceptions = False
            else:
                kwargs["raise_errors"] = True
            raw = yf.Ticker(ticker).history(**kwargs)
            if "Stock Splits" in raw:
                for date,value in raw["Stock Splits"].items():
                    if not math.isfinite(float(value)):
                        raise ValueError("Invalid split metadata")
                    actions[label(date)] = float(value)
            return raw
        frame = fetch_daily(ticker,start,end,required,fetcher=get,tail_fetcher=get)
        frame["Stock Splits"] = [actions.get(label(d),0.0) for d in frame.index]
        result[ticker] = frame
    return result


def save(path,state):
    payload = json.dumps(dict(sha256=digest(state),state=state),indent=2,allow_nan=False)
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=path.parent,delete=False) as f:
        temp = Path(f.name)
        f.write(payload); f.flush(); os.fsync(f.fileno())
    try:
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def main():
    import exchange_calendars as xcals
    import run_recent_blend
    from swingbot.scanner import load_tickers
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("plan","settle","daily","status"))
    parser.add_argument("--directory",default="reports/paper_forward")
    args = parser.parse_args()
    directory = Path(args.directory); directory.mkdir(parents=True,exist_ok=True)
    path,lock = directory/"state.json",directory/".lock"
    fd = os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.close(fd)
        now,calendar = clock(),xcals.get_calendar("XNYS")
        tickers = sorted(set(load_tickers("config/tickers.txt")))
        source_hash = hashlib.sha256(Path(__file__).read_bytes()+Path(run_recent_blend.__file__).read_bytes()).hexdigest()
        state = new_state(tickers,source_hash,now)
        if path.exists():
            envelope = json.loads(path.read_text(encoding="utf-8")); state = envelope["state"]
            if envelope["sha256"]!=digest(state) or state["rules"]!=RULES or state["tickers"]!=tickers or state["source_hash"]!=source_hash:
                raise ValueError("State integrity/config/source changed; explicit version review required")
            previous = None
            for e in state["events"]:
                if e["previous_hash"]!=previous or e["hash"]!=digest({k:v for k,v in e.items() if k!="hash"}):
                    raise ValueError("Broken event chain")
                previous = e["hash"]
        if args.command!="status":
            day = latest_complete(calendar,now)
            bars = fetch_bars(tickers,day,calendar)
            while args.command in ("settle","daily") and state["last_session"] is not None and state["last_session"]<day:
                session = label(calendar.next_session(pd.Timestamp(state["last_session"])))
                prices = {t:{k:float(v) for k,v in bars[t].loc[pd.Timestamp(session)].to_dict().items()} for t in tickers}
                state = settle(state,session,prices,calendar,now)
                save(path,state)
                if args.command=="settle":
                    break
            if args.command in ("plan","daily"):
                state = make_plan(state,bars,calendar,now)
            save(path,state)
        report = summary(state)
        (directory/"status.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
        pd.DataFrame([dict(model=m,**t) for m,b in state["books"].items() for t in b["trades"]],columns=["model","ticker","entry_date","exit_date","shares","entry_fill","exit_fill","exit_reason","net_pnl","realized_r","held_sessions","plan_hash"]).to_csv(directory/"closed_trades.csv",index=False)
        (directory/"events.jsonl").write_text("\n".join(json.dumps(e,sort_keys=True,allow_nan=False) for e in state["events"])+"\n",encoding="utf-8")
        print(json.dumps(report,indent=2,allow_nan=False))
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
