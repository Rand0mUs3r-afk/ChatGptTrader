"""2026 YTD entries, maximum 45 trading sessions. Separate research; no orders."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from types import FunctionType
import pandas as pd
import october_15_session as prior
import backtest_october_2026 as engine
from history_45_session import sample_feasibility

START, END = pd.Timestamp("2026-01-01"),pd.Timestamp("2027-01-01")
HOLD = 45


def configured_function(function,**overrides):
    result = FunctionType(function.__code__,dict(function.__globals__,**overrides),function.__name__,function.__defaults__,function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


simulate = configured_function(engine.simulate,START=START,END=END)
build_book = configured_function(prior.build_book,HOLD=HOLD)


def load_market(market,out,now):
    import exchange_calendars as xcals
    from history_45_session import fetch_daily
    from swingbot.scanner import load_tickers
    calendar = xcals.get_calendar("XNYS" if market == "us" else "XTSE")
    history_start = START-pd.DateOffset(years=10)
    sessions = calendar.sessions_in_range(history_start,END-pd.Timedelta(days=1))
    complete = [s for s in sessions if calendar.session_close(s)+pd.Timedelta(minutes=20)<=now]
    if not complete or pd.Timestamp(complete[-1]).tz_localize(None)<START:
        raise ValueError("No completed 2026 sessions")
    cutoff = pd.Timestamp(complete[-1]).tz_localize(None).normalize()+pd.Timedelta(days=1)
    required = pd.DatetimeIndex(complete[-20:]).tz_localize(None).normalize()
    tickers = sorted(set(load_tickers("config/tickers.txt" if market == "us" else "config/tickers_tsx.txt")))
    eligibility = {t:START for t in tickers}
    if market == "tsx":
        original = set(load_tickers("config/tickers_tsx_october_baseline.txt"))
        added = pd.read_csv("config/tsx_added_eligibility.csv")
        known = {r.ticker:pd.Timestamp(r.eligible_from).normalize() for r in added.itertuples()}
        for ticker in set(tickers)-original:
            if ticker not in known:
                raise ValueError(f"{ticker}: missing universe date")
            eligibility[ticker] = known[ticker]
    data,coverage,excluded = {},{},{}
    directory = out/market
    directory.mkdir(parents=True,exist_ok=True)
    for ticker in tickers:
        if eligibility[ticker]>=cutoff:
            excluded[ticker] = "NOT_YET_DATE_ELIGIBLE"
            continue
        frame = fetch_daily(ticker,history_start,cutoff,required)
        expected = pd.DatetimeIndex(calendar.sessions_in_range(frame.index[0],frame.index[-1])).tz_localize(None).normalize()
        if not frame.index.equals(expected):
            raise ValueError(f"{ticker}: historical session gaps")
        if sum(frame.index<START)<60:
            excluded[ticker] = "FEWER_THAN_60_PRE_JANUARY_SESSIONS"
            continue
        frame.attrs["ticker"] = ticker
        data[ticker] = frame
        snapshot = frame.to_csv(index_label="Date")
        (directory/f"bars_{ticker}.csv").write_text(snapshot,encoding="utf-8")
        coverage[ticker] = dict(requested_start=str(history_start.date()),first=str(frame.index[0].date()),last=str(frame.index[-1].date()),bars=len(frame),sha256=hashlib.sha256(snapshot.encode()).hexdigest())
    if not data:
        raise ValueError("Empty usable universe")
    return data,eligibility,calendar,dict(eligible_from={t:str(d.date()) for t,d in eligibility.items()},excluded=excluded,coverage=coverage)


def deadline(calendar,entry_date):
    start = pd.Timestamp(entry_date)
    sessions = calendar.sessions_in_range(start,start+pd.Timedelta(days=120))
    return str(pd.Timestamp(sessions[HOLD-1]).date())


def main():
    from run_recent_blend import features
    from checked_history import PRICE_BASIS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market",choices=("us","tsx","both"),default="both")
    parser.add_argument("--equity-us",type=float,default=1000)
    parser.add_argument("--equity-tsx",type=float,default=1000)
    parser.add_argument("--share-mode",choices=("fractional","whole"),default="fractional")
    args = parser.parse_args()
    if any(not math.isfinite(v) or v<=0 for v in (args.equity_us,args.equity_tsx)):
        raise ValueError("Invalid equity")
    out = Path("reports/year_2026_45_session")
    out.mkdir(parents=True,exist_ok=True)
    now,results,universes,feasibility = pd.Timestamp.now(tz="UTC"),[],{},[]
    for market in (("us","tsx") if args.market == "both" else (args.market,)):
        full,eligibility,calendar,universes[market] = load_market(market,out,now)
        cached_full = {t:features(frame) for t,frame in full.items()}
        dates,data,cached = prior.align_portfolio(full,cached_full)
        universes[market]["portfolio_common_history_start"] = str(dates[0].date())
        for strategy in prior.STRATEGIES:
            books = {t:build_book(frame,cached_full[t],strategy) for t,frame in full.items()}
            (out/market/f"{strategy}_calibration_audit.json").write_text(json.dumps(books,indent=2,allow_nan=False),encoding="utf-8")
            checks = []
            for ticker,frame in full.items():
                first = int(frame.index.searchsorted(max(START,eligibility[ticker]),side="left"))
                for boundary,known_bars in (("first_eligible_entry_open",first),("latest_entry_open",len(frame)-1)):
                    checks.append(dict(market=market,strategy=strategy,ticker=ticker,boundary=boundary,
                        entry_date=str(frame.index[known_bars].date()),**sample_feasibility(books[ticker],known_bars)))
            feasibility.extend(checks)
            pd.DataFrame(checks).to_csv(out/market/f"{strategy}_feasibility_decisions.csv",index=False)
            print(f"Pre-entry sample feasibility {market}/{strategy}: {dict(Counter(r['sample_feasibility'] for r in checks))}",flush=True)
            for model in ("empirical","fixed_2r_control"):
                directory = out/market/model
                directory.mkdir(parents=True,exist_ok=True)
                diagnostics = []
                summary,journal,daily,decisions = simulate(data,cached,strategy,HOLD,
                    equity=args.equity_us if market == "us" else args.equity_tsx,
                    assessor=prior.target_assessor(books,dates,diagnostics,model,full),eligibility=eligibility,fractional=args.share_mode == "fractional")
                selected = {(d["ticker"],d["entry_date"]):d for d in diagnostics}
                for trade in journal:
                    trade["latest_exit_date"] = deadline(calendar,trade["entry_date"])
                    for key,value in selected[(trade["ticker"],trade["entry_date"])].items():
                        if key not in trade:
                            trade[key] = value
                summary.update(market=market,currency="USD" if market == "us" else "CAD",variant=model,
                    decision_counts=dict(Counter(d["status"] for d in decisions)),
                    full_horizon_mature_entries=sum(t["latest_exit_date"]<=summary["asof"] for t in journal))
                summary["activity_status"] = "NO_TRADES_NOT_EVALUABLE" if summary["entries"]==0 else "OPEN_POSITIONS_ONLY" if summary["closed_trades"]==0 else "RESEARCH_NOT_VALIDATED"
                results.append(summary)
                stem = strategy+"_h45"
                (directory/f"{stem}_journal.json").write_text(json.dumps(journal,indent=2,allow_nan=False),encoding="utf-8")
                for suffix,rows,empty_columns in (("journal",journal,["ticker","entry_date","closed","net_pnl"]),("daily_equity",daily,["date","marked_equity"]),("decisions",decisions,["entry_date","ticker","status"]),("assessment_decisions",diagnostics,["ticker","target_status"])):
                    pd.DataFrame(rows,columns=list(dict.fromkeys(k for row in rows for k in row)) if rows else empty_columns).to_csv(directory/f"{stem}_{suffix}.csv",index=False)
    notes = ("2026 YEAR-TO-DATE ENTRY RESEARCH; maximum 45 TRADING SESSIONS, entry is session one. "
        "Entries from January 1 through latest completed 2026 exchange session, never future prices. SL/TP "
        "may exit earlier; open positions are marked separately, not forced wins/losses. Up to ten years "
        "of pre-2026 history are requested and retained when available, without the older five-year truncation. "
        "Per-ticker/strategy feasibility audits use only outcomes matured before the first eligible entry "
        "open and latest entry open. Feasible sample counts do NOT imply positive edge or trade approval. "
        "Later pre-entry matured 2026 outcomes may update the model causally. Same empirical target grid, "
        "20 calibration/10 qualifying walk-forward minimums, positive mean net-R checks and 30-example "
        "training window as the 15-session experiment. Targets/stops are not mechanically scaled with "
        "holding time. Shorter-listed stocks may lack sufficient empirical evidence and are rejected, "
        "not granted looser thresholds. At least 60 pre-January bars are required for price-feature "
        "warm-up; exclusions are disclosed. This is a retrospective current-baseline-watchlist study, "
        "NOT a reconstructed point-in-time 2026 universe. Known later TSX additions retain their recorded "
        "eligibility dates, not January 1. Historical hit rates are descriptive, not forecast probabilities; "
        "old regimes and selection bias remain. Compression/balanced/trend-family signals, original "
        "pattern stops, empirical targets and labeled fixed-2R controls. Separate USD/CAD accounts, one "
        "position at a time, 25% allocation and 1.5% planned equity-risk caps, 15 bps/side; gaps can exceed "
        "planned risk. No commissions or dividend cash, daily stop-first fills, fractional broker/order "
        "eligibility unverified. Zero entries are not evaluable. Independent scenarios must not be summed "
        "as one portfolio. No orders or live strategy promotion. Original October experiments and reports "
        "remain unchanged.")
    manifest = dict(experiment="2026_ytd_45_session_empirical_targets",generated_at=str(now),entry_start=str(START.date()),entry_end_exclusive=str(END.date()),max_hold_sessions=HOLD,share_mode=args.share_mode,price_basis=PRICE_BASIS,notes=notes,universes=universes,calibration_feasibility=feasibility,results=results)
    (out/"results.json").write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding="utf-8")
    table = pd.DataFrame(results)
    table.to_csv(out/"results.csv",index=False)
    fields = ["market","variant","strategy","asof","entries","closed_trades","wins","losses","open_positions","full_horizon_mature_entries","ending_marked_equity","total_return_pct","max_marked_drawdown_pct","activity_status"]
    text = "# 2026 year-to-date entries - maximum 45 trading sessions\n\n"+notes+"\n\n```text\n"+table[fields].to_string(index=False)+"\n```\n"
    text += "\n## Pre-entry sample feasibility (not trade approval)\n\n"
    for market in universes:
        for strategy in prior.STRATEGIES:
            for boundary in ("first_eligible_entry_open","latest_entry_open"):
                counts = Counter(r["sample_feasibility"] for r in feasibility if r["market"]==market and r["strategy"]==strategy and r["boundary"]==boundary)
                text += f"- {market}/{strategy}/{boundary}: {dict(counts)}\n"
    (out/"summary.md").write_text(text,encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
