"""October-only stop/target bundle comparison. Research, not live strategy selection."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import pandas as pd
from backtest_october_2026 import START, END, MODES, simulate


def activity_status(summary):
    if summary["entries"] == 0:
        return "NO_TRADES_NOT_EVALUABLE"
    if summary["closed_trades"] == 0:
        return "OPEN_POSITIONS_ONLY"
    return "RESEARCH_NOT_VALIDATED"


def evaluator(target_model, dates, diagnostics, adaptive=None):
    from assess_targets import assess, net_rr, MIN_NET_RR
    if target_model not in ("fixed_2r","data_checked"):
        raise ValueError("Unknown target model")
    adaptive = adaptive or assess
    def evaluate(history,row,cached):
        entry,stop = float(row["provisional_entry"]),float(row["stop"])
        if target_model == "fixed_2r":
            target = entry+2*(entry-stop)
            ratio = float(net_rr(entry,stop,target))
            check = dict(assessed_target=target,assessed_net_rr=ratio,historical_examples=None,
                walkforward_examples=None,target_status="EXPERIMENTAL_CANDIDATE" if ratio>=MIN_NET_RR else "SKIP_LOW_NET_RR")
        else:
            check,_ = adaptive(history,row,cached)
        prior = history.Close.shift()
        true_range = pd.concat([history.High-history.Low,(history.High-prior).abs(),(history.Low-prior).abs()],axis=1).max(axis=1)
        atr = float(true_range.iloc[-14:].mean())
        median = check.get("historical_median_mfe_r")
        empirical_cap = entry+float(median)*(entry-stop) if median is not None else None
        high = check.get("nearest_confirmed_high")
        resistance_cap = float(high)-0.1*atr if high is not None else None
        binding = "fixed_2r_benchmark" if target_model == "fixed_2r" else (
            "insufficient_estimation_data" if empirical_cap is None else
            "confirmed_high_cap" if resistance_cap is not None and resistance_cap<empirical_cap else "median_excursion_cap")
        diagnostics.append(dict(ticker=history.attrs.get("ticker","UNKNOWN"),signal_date=str(history.index[-1].date()),
            entry_date=str(dates[len(history)].date()),entry_open=entry,stop=stop,atr14=atr,
            stop_distance_atr=(entry-stop)/atr if atr>0 else None,fixed_2r_reference=entry+2*(entry-stop),
            empirical_target_cap=empirical_cap,resistance_target_cap=resistance_cap,binding_target_constraint=binding,
            assessed_target=check.get("assessed_target"),net_rr=check.get("assessed_net_rr"),status=check["target_status"],
            historical_examples=check.get("historical_examples"),walkforward_examples=check.get("walkforward_examples"),
            walkforward_mean_net_r=check.get("walkforward_mean_net_r"),
            historical_gate="NOT_APPLIED_BENCHMARK_ONLY" if target_model == "fixed_2r" else "APPLIED"))
        return check,{}
    return evaluate


def load_market(market,out,now):
    import exchange_calendars as xcals
    from checked_history import fetch_daily
    from swingbot.scanner import load_tickers
    calendar = xcals.get_calendar("XNYS" if market == "us" else "XTSE")
    sessions = calendar.sessions_in_range(START-pd.DateOffset(years=5),END-pd.Timedelta(days=1))
    complete = [s for s in sessions if calendar.session_close(s)+pd.Timedelta(minutes=20)<=now]
    if not complete or pd.Timestamp(complete[-1]).tz_localize(None)<START:
        raise ValueError("No completed October sessions")
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
    excluded = [t for t in tickers if eligibility[t]>=cutoff]
    data,coverage = {},{}
    directory = out/market
    directory.mkdir(parents=True,exist_ok=True)
    for ticker in tickers:
        if ticker in excluded:
            continue
        frame = fetch_daily(ticker,START-pd.DateOffset(years=5),cutoff,required)
        expected = pd.DatetimeIndex(calendar.sessions_in_range(frame.index[0],frame.index[-1])).tz_localize(None).normalize()
        if not frame.index.equals(expected) or sum(frame.index<START)<300:
            raise ValueError(f"{ticker}: incomplete historical coverage")
        frame.attrs["ticker"] = ticker
        data[ticker] = frame
        snapshot = frame.to_csv(index_label="Date")
        (directory/f"bars_{ticker}.csv").write_text(snapshot,encoding="utf-8")
        coverage[ticker] = dict(first=str(frame.index[0].date()),last=str(frame.index[-1].date()),bars=len(frame),
            sha256=hashlib.sha256(snapshot.encode()).hexdigest())
    if not data:
        raise ValueError("Empty eligible universe")
    return data,eligibility,dict(not_yet_eligible=excluded,coverage=coverage)


def raw_signals(data,cached,mode,eligibility):
    from run_recent_blend import candidate,FAMILIES
    weights = {g:1/len(FAMILIES) for g in FAMILIES}
    dates = next(iter(data.values())).index
    return sum(1 for i,date in enumerate(dates) if START<=date<END and i>0
        for ticker in data if date>=eligibility[ticker] and candidate(cached[ticker][i-1],mode,weights,False))


def main():
    from run_recent_blend import features
    from assess_structural_risk import risk_features
    from checked_history import PRICE_BASIS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market",choices=("us","tsx","both"),default="both")
    parser.add_argument("--equity-us",type=float,default=1000)
    parser.add_argument("--equity-tsx",type=float,default=1000)
    parser.add_argument("--share-mode",choices=("fractional","whole"),default="fractional")
    args = parser.parse_args()
    if any(not math.isfinite(x) or x<=0 for x in (args.equity_us,args.equity_tsx)):
        raise ValueError("Invalid scenario equity")
    out = Path("reports/october_2026")
    out.mkdir(parents=True,exist_ok=True)
    now,results,universes = pd.Timestamp.now(tz="UTC"),[],{}
    for market in (("us","tsx") if args.market == "both" else (args.market,)):
        data,eligibility,universes[market] = load_market(market,out,now)
        dates = next(iter(data.values())).index
        pattern = {t:features(frame) for t,frame in data.items()}
        for mode in MODES:
            structural = {t:risk_features(frame,mode,pattern[t]) for t,frame in data.items()}
            for stop_model,cached in (("pattern",pattern),("structural",structural)):
                count_raw = raw_signals(data,cached,mode,eligibility)
                for target_model in ("fixed_2r","data_checked"):
                    variant = stop_model+"__"+target_model
                    directory = out/market/variant
                    directory.mkdir(parents=True,exist_ok=True)
                    for hold in (5,7):
                        diagnostics = []
                        summary,journal,daily,decisions = simulate(data,cached,mode,hold,
                            equity=args.equity_us if market == "us" else args.equity_tsx,
                            assessor=evaluator(target_model,dates,diagnostics),eligibility=eligibility,
                            fractional=args.share_mode == "fractional")
                        counts = Counter(d["status"] for d in decisions)
                        summary.update(market=market,currency="USD" if market == "us" else "CAD",variant=variant,
                            stop_model=stop_model,target_model=target_model,raw_signal_checks=count_raw,
                            evaluated_candidate_checks=len(decisions),rejection_counts=dict(counts),
                            low_rr_rejections=counts["SKIP_LOW_NET_RR"],no_upside_rejections=counts["SKIP_NO_SUPPORTED_UPSIDE"],
                            insufficient_history=counts["INSUFFICIENT_HISTORY"],insufficient_walkforward=counts["INSUFFICIENT_WALKFORWARD"],
                            nonpositive_walkforward=counts["SKIP_NONPOSITIVE_WALKFORWARD"],
                            sizing_rejections=sum(counts[k] for k in ("SKIP_UNAFFORDABLE","FRACTION_STEP_TOO_SMALL","BELOW_MIN_NOTIONAL","WHOLE_SHARE_ALLOCATION_LIMIT","WHOLE_SHARE_RISK_LIMIT")))
                        summary["activity_status"] = activity_status(summary)
                        results.append(summary)
                        trial=f"{mode}_h{hold}"
                        (directory/f"{trial}_journal.json").write_text(json.dumps(journal,indent=2,allow_nan=False),encoding="utf-8")
                        pd.DataFrame(journal,columns=list(journal[0]) if journal else ["ticker","entry_date","closed","net_pnl"]).to_csv(directory/f"{trial}_journal.csv",index=False)
                        pd.DataFrame(daily).to_csv(directory/f"{trial}_daily_equity.csv",index=False)
                        pd.DataFrame(decisions,columns=["entry_date","ticker","status","net_rr"]).to_csv(directory/f"{trial}_decisions.csv",index=False)
                        pd.DataFrame(diagnostics,columns=list(diagnostics[0]) if diagnostics else ["ticker","status"]).to_csv(directory/f"{trial}_assessment_decisions.csv",index=False)
    notes = ("OCTOBER-ONLY RESEARCH COMPARISON, not a live strategy change or automatic winner selection. "
        "Four bundles: pattern/structural stops crossed with fixed-2R/data-checked targets. Same eligible universe, "
        "share mode, account limits, ranking, costs and daily fill rules. Each row is a separate account; do not sum "
        "variants as one portfolio. Fixed-2R is an explicitly unvalidated benchmark: it retains the net-RR >=1.25 "
        "filter but does NOT apply historical target/sample/walk-forward gates. Data-checked includes those gates. "
        "This compares target-engine bundles, not target distance alone; rejection diagnostics expose the differences. "
        "Raw signals include all eligible stock/date signals, even while positions are held; evaluated checks include "
        "only visited candidates while flat and stop after selection. Counts are first-gate decisions, not proof that "
        "later gates passed. Original pattern checks and structural stop rules are unchanged. Pre-entry data only "
        "for signals, stops and historical validation; next-open entry. Price, fractional execution, slippage, gap, "
        "no-dividend/commission and development-sample limitations of the October engine remain. New TSX additions "
        "are eligible only from October 23. Open positions are not forced wins/losses. Zero entries are explicitly "
        "NOT EVALUABLE, not a successful low-risk strategy. No guarantee of profits or trades; no orders placed.")
    manifest = dict(generated_at=str(now),comparison=True,entry_start="2026-10-01",entry_end_exclusive="2026-11-01",
        share_mode=args.share_mode,price_basis=PRICE_BASIS,notes=notes,universes=universes,results=results)
    (out/"results.json").write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding="utf-8")
    table = pd.DataFrame(results)
    table.to_csv(out/"results.csv",index=False)
    table[["market","variant","strategy","max_hold_sessions","raw_signal_checks","evaluated_candidate_checks","sizing_rejections","low_rr_rejections","no_upside_rejections","insufficient_history","insufficient_walkforward","nonpositive_walkforward","entries","activity_status"]].to_csv(out/"filter_funnel_decisions.csv",index=False)
    text = f"# October 2026 model comparison ({args.share_mode} shares)\n\n{notes}\n\n"
    for market,info in universes.items():
        if info["not_yet_eligible"]:
            text += f"{market.upper()} additions not yet eligible: {', '.join(info['not_yet_eligible'])}.\n\n"
    text += "| Market | Variant | Strategy | Hold | As of | Entries | Closed | Won | Lost | Open | Realized P&L | Unrealized P&L | Marked equity | Return % | Drawdown % | Activity status |\n"
    text += "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n"
    for r in results:
        text += (f"| {r['market']} ({r['currency']}) | {r['variant']} | {r['strategy']} | {r['max_hold_sessions']} | {r['asof']} "
            f"| {r['entries']} | {r['closed_trades']} | {r['wins']} | {r['losses']} | {r['open_positions']} "
            f"| {r['realized_net_pnl']:.2f} | {r['unrealized_estimated_liquidation_pnl']:.2f} | {r['ending_marked_equity']:.2f} "
            f"| {r['total_return_pct']:.2f} | {r['max_marked_drawdown_pct']:.2f} | {r['activity_status']} |\n")
    text += "\n## Rejection audit\n\n| Market | Variant | Strategy | Hold | Raw signals | Evaluated | Sizing | Low RR | No upside | History | Walk-forward N | Walk-forward mean | Entries |\n"
    text += "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for r in results:
        text += (f"| {r['market']} | {r['variant']} | {r['strategy']} | {r['max_hold_sessions']} | {r['raw_signal_checks']} "
            f"| {r['evaluated_candidate_checks']} | {r['sizing_rejections']} | {r['low_rr_rejections']} | {r['no_upside_rejections']} "
            f"| {r['insufficient_history']} | {r['insufficient_walkforward']} | {r['nonpositive_walkforward']} | {r['entries']} |\n")
    (out/"summary.md").write_text(text,encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
