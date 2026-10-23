"""October-entry, maximum-15-session empirical-target experiment. No orders."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

HOLD = 15
GRID = (0.5,0.75,1.0,1.25,1.5,2.0)
STRATEGIES = ("compression_family","balanced_blend","trend_family")
MIN_TRAIN, MIN_WF, TRAIN_WINDOW = 20,10,30


def best_target(records):
    means = np.array([r["net_r"] for r in records],dtype=float).mean(axis=0)
    if not np.isfinite(means).all():
        raise ValueError("Invalid calibration outcomes")
    chosen = int(np.argmax(means))
    return chosen,float(means[chosen])


def calibrate(records, asof_index, entry, stop):
    from assess_targets import net_rr
    if not 0 < stop < entry:
        raise ValueError("Invalid entry/stop")
    past = [r for r in records if r["end_index"]<=asof_index]
    result = dict(assessed_target=None,assessed_net_rr=None,historical_examples=len(past),
        walkforward_examples=0,walkforward_mean_net_r=None,selected_raw_r=None,
        calibration_mean_net_r=None,calibration_target_hit_pct=None,walkforward_target_hit_pct=None,
        walkforward_standard_error=None)
    if len(past)<MIN_TRAIN:
        return dict(**result,target_status="INSUFFICIENT_CALIBRATION")
    training = past[-TRAIN_WINDOW:]
    chosen,mean = best_target(training)
    forward,hit = [],[]
    for k in range(MIN_TRAIN,len(past)):
        index,edge = best_target(past[max(0,k-TRAIN_WINDOW):k])
        if edge>0:
            forward.append(float(past[k]["net_r"][index]))
            hit.append(bool(past[k]["hit"][index]))
    target = entry+GRID[chosen]*(entry-stop)
    ratio = float(net_rr(entry,stop,target))
    wf_mean = float(np.mean(forward)) if forward else None
    result.update(assessed_target=float(target),assessed_net_rr=ratio,selected_raw_r=GRID[chosen],
        calibration_mean_net_r=mean,calibration_target_hit_pct=float(100*np.mean([r["hit"][chosen] for r in training])),
        walkforward_examples=len(forward),walkforward_mean_net_r=wf_mean,
        walkforward_target_hit_pct=float(100*np.mean(hit)) if hit else None,
        walkforward_standard_error=float(np.std(forward,ddof=1)/math.sqrt(len(forward))) if len(forward)>1 else None)
    status = ("SKIP_NO_CALIBRATION_EDGE" if mean<=0 else "INSUFFICIENT_WALKFORWARD" if len(forward)<MIN_WF
        else "SKIP_NONPOSITIVE_WALKFORWARD" if wf_mean<=0 else "SKIP_COSTS_EXCEED_TARGET" if ratio<=0
        else "EXPERIMENTAL_CANDIDATE")
    return dict(**result,target_status=status)


def build_book(frame,cached,strategy):
    from run_recent_blend import candidate,FAMILIES
    from assess_targets import trial
    weights = {g:1/len(FAMILIES) for g in FAMILIES}
    records,blocked_until = [],-1
    for i in range(50,len(frame)-HOLD):
        if i<blocked_until:
            continue
        signal = candidate(cached[i],strategy,weights,False)
        if signal is None:
            continue
        entry = float(frame.Open.iloc[i+1])
        stop = float(signal["stop"])
        if entry<=stop:
            continue
        outcomes = [trial(frame,i,stop,HOLD,entry+r*(entry-stop)) for r in GRID]
        if any(o is None for o in outcomes):
            continue
        records.append(dict(signal_index=i,end_index=i+HOLD,signal_date=str(frame.index[i].date()),
            horizon_end=str(frame.index[i+HOLD].date()),net_r=[float(o["net_r"]) for o in outcomes],
            hit=[bool(o["target_hit"]) for o in outcomes]))
        blocked_until = i+HOLD
    return records


def target_assessor(books,dates,diagnostics,model,full_data=None):
    from assess_targets import net_rr,MIN_NET_RR
    if model not in ("empirical","fixed_2r_control"):
        raise ValueError("Unknown target model")
    def evaluate(history,row,cached):
        ticker = history.attrs["ticker"]
        entry,stop = float(row["provisional_entry"]),float(row["stop"])
        signal_index,source_history = len(history)-1,history
        if full_data is not None:
            signal_index = int(full_data[ticker].index.get_loc(history.index[-1]))
            source_history = full_data[ticker].iloc[:signal_index+1]
        if model == "empirical":
            check = calibrate(books[ticker],signal_index,entry,stop)
        else:
            target = entry+2*(entry-stop)
            ratio = float(net_rr(entry,stop,target))
            check = dict(assessed_target=target,assessed_net_rr=ratio,historical_examples=None,walkforward_examples=None,
                target_status="EXPERIMENTAL_CANDIDATE" if ratio>=MIN_NET_RR else "SKIP_LOW_NET_RR",
                selected_raw_r=2.0,walkforward_mean_net_r=None)
        highs = source_history.High.to_numpy(dtype=float)
        levels = [highs[j] for j in range(max(2,len(highs)-60),len(highs)-2)
            if highs[j]>max(highs[j-2:j]) and highs[j]>max(highs[j+1:j+3]) and highs[j]>entry]
        resistance = float(min(levels)) if levels else None
        target = check.get("assessed_target")
        diagnostics.append(dict(ticker=ticker,entry_date=str(dates[len(history)].date()),signal_date=str(history.index[-1].date()),
            entry_open=entry,stop=stop,target_model=model,nearest_confirmed_high=resistance,
            requires_resistance_break=bool(target is not None and resistance is not None and target>resistance),**check))
        return check,{}
    return evaluate


def align_portfolio(data,cached):
    start = max(f.index[0] for f in data.values())
    dates = next(iter(data.values())).index
    dates = dates[dates>=start]
    aligned,features = {},{}
    for ticker,frame in data.items():
        if not dates.isin(frame.index).all():
            raise ValueError("Missing portfolio exchange sessions")
        aligned[ticker] = frame.loc[dates].copy()
        features[ticker] = [cached[ticker][int(frame.index.get_loc(date))] for date in dates]
    return dates,aligned,features


def main():
    import exchange_calendars as xcals
    from run_recent_blend import features
    from compare_october_models import load_market,raw_signals,activity_status
    from backtest_october_2026 import simulate
    from checked_history import PRICE_BASIS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market",choices=("us","tsx","both"),default="both")
    parser.add_argument("--equity-us",type=float,default=1000)
    parser.add_argument("--equity-tsx",type=float,default=1000)
    parser.add_argument("--share-mode",choices=("fractional","whole"),default="fractional")
    args = parser.parse_args()
    if any(not math.isfinite(e) or e<=0 for e in (args.equity_us,args.equity_tsx)):
        raise ValueError("Invalid equity")
    out = Path("reports/october_2026")
    out.mkdir(parents=True,exist_ok=True)
    now,results,universes = pd.Timestamp.now(tz="UTC"),[],{}
    for market in (("us","tsx") if args.market == "both" else (args.market,)):
        data,eligibility,universes[market] = load_market(market,out,now)
        full_data = data
        full_cached = {t:features(f) for t,f in full_data.items()}
        dates,data,cached = align_portfolio(full_data,full_cached)
        universes[market]["portfolio_common_history_start"] = str(dates[0].date())
        calendar = xcals.get_calendar("XNYS" if market == "us" else "XTSE")
        for strategy in STRATEGIES:
            books = {t:build_book(frame,full_cached[t],strategy) for t,frame in full_data.items()}
            (out/market/f"{strategy}_calibration_audit.json").write_text(json.dumps(books,indent=2,allow_nan=False),encoding="utf-8")
            for model in ("empirical","fixed_2r_control"):
                directory = out/market/model
                directory.mkdir(parents=True,exist_ok=True)
                diagnostics = []
                summary,journal,daily,decisions = simulate(data,cached,strategy,HOLD,
                    equity=args.equity_us if market == "us" else args.equity_tsx,
                    assessor=target_assessor(books,dates,diagnostics,model,full_data),eligibility=eligibility,
                    fractional=args.share_mode == "fractional")
                by_entry = {(d["ticker"],d["entry_date"]):d for d in diagnostics}
                for trade in journal:
                    sessions = calendar.sessions_in_range(pd.Timestamp(trade["entry_date"]),pd.Timestamp(trade["entry_date"])+pd.Timedelta(days=45))
                    trade["latest_exit_date"] = str(pd.Timestamp(sessions[HOLD-1]).date())
                    detail = by_entry[(trade["ticker"],trade["entry_date"])]
                    for key in ("selected_raw_r","calibration_mean_net_r","calibration_target_hit_pct","walkforward_mean_net_r","walkforward_target_hit_pct","walkforward_standard_error","nearest_confirmed_high","requires_resistance_break"):
                        trade[key] = detail.get(key)
                counts = Counter(d["status"] for d in decisions)
                summary.update(market=market,currency="USD" if market == "us" else "CAD",variant=model,
                    raw_signal_checks=raw_signals(data,cached,strategy,eligibility),evaluated_candidate_checks=len(decisions),
                    decision_counts=dict(counts),full_horizon_mature_entries=sum(t["latest_exit_date"]<=summary["asof"] for t in journal),
                    early_exits=sum(t["closed"] and t["held_sessions"]<HOLD for t in journal))
                summary["activity_status"] = activity_status(summary)
                results.append(summary)
                stem = strategy+"_h15"
                (directory/f"{stem}_journal.json").write_text(json.dumps(journal,indent=2,allow_nan=False),encoding="utf-8")
                pd.DataFrame(journal,columns=list(journal[0]) if journal else ["ticker","entry_date","closed","net_pnl"]).to_csv(directory/f"{stem}_journal.csv",index=False)
                pd.DataFrame(daily).to_csv(directory/f"{stem}_daily_equity.csv",index=False)
                pd.DataFrame(decisions,columns=["entry_date","ticker","status","net_rr"]).to_csv(directory/f"{stem}_decisions.csv",index=False)
                pd.DataFrame(diagnostics,columns=list(diagnostics[0]) if diagnostics else ["ticker","target_status"]).to_csv(directory/f"{stem}_assessment_decisions.csv",index=False)
    notes = ("EXPERIMENTAL OCTOBER-ENTRY RESEARCH, maximum 15 TRADING SESSIONS, counting entry as session one; "
        "SL/TP may exit sooner. October performance ends at the latest completed October session; later exits "
        "are not fabricated. Most recent entries may lack a complete 15-session outcome; open positions and "
        "full-horizon maturity are shown separately. Earlier bars are calibration-only. Portfolio dates are aligned, "
        "but calibration keeps each ticker's full available history, including for shorter-listed names. Compression and balanced "
        "blend retain original pattern stops; trend_family is an alternative trend/momentum-family signal, not "
        "a new SMA-pullback strategy. Stops are never tightened merely to improve RR. Empirical targets test "
        "the predefined raw-R grid [0.5,0.75,1,1.25,1.5,2] on nonoverlapping same-stock/same-strategy examples. "
        "At least 20 matured examples are needed; select the highest mean net R from at most 30 earlier examples, "
        "breaking ties toward the lower target. Each historical walk-forward selection uses only its earlier "
        "completed examples. Require at least 10 positive-training-edge walk-forward entries and positive mean "
        "walk-forward net R. Current target must cover modeled costs; there is NO unconditional 1.25 RR floor "
        "in empirical mode. Nearest confirmed resistance is a warning, not an automatic hard cap. These are "
        "fixed research choices, not validated optimal parameters. Historical hit rates and standard errors "
        "are descriptive, NOT calibrated future probabilities or guaranteed exits. The fixed-2R control is "
        "an unvalidated reference with its original 1.25 net-RR gate and no historical gates. Same universe "
        "dates, ranking, fractional assumptions, 25% allocation cap, 1.5% equity planned-risk cap and 15 bps/side. "
        "No commissions/dividend cash; daily stop-first and gap-risk assumptions; broker fractional protective "
        "orders unverified. Separate accounts, no FX pooling, no orders, no automatic strategy promotion. "
        "Current-universe/development-sample bias remains; original 5/7-session results stay preserved.")
    manifest = dict(generated_at=str(now),experiment="15_session_empirical_targets",max_hold_sessions=HOLD,
        share_mode=args.share_mode,entry_start="2026-10-01",entry_end_exclusive="2026-11-01",price_basis=PRICE_BASIS,
        target_grid=list(GRID),notes=notes,universes=universes,results=results)
    (out/"results.json").write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding="utf-8")
    pd.DataFrame(results).to_csv(out/"results.csv",index=False)
    text = f"# October entries - maximum 15 sessions ({args.share_mode})\n\n{notes}\n\n"
    text += "| Market | Target model | Strategy | Entries | Closed | Won | Lost | Open | Full-horizon mature | Realized P&L | Unrealized P&L | Equity | Return % | Drawdown % | Status |\n"
    text += "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n"
    for r in results:
        text += (f"| {r['market']} ({r['currency']}) | {r['variant']} | {r['strategy']} | {r['entries']} | {r['closed_trades']} "
            f"| {r['wins']} | {r['losses']} | {r['open_positions']} | {r['full_horizon_mature_entries']} "
            f"| {r['realized_net_pnl']:.2f} | {r['unrealized_estimated_liquidation_pnl']:.2f} | {r['ending_marked_equity']:.2f} "
            f"| {r['total_return_pct']:.2f} | {r['max_marked_drawdown_pct']:.2f} | {r['activity_status']} |\n")
    text += "\n## Evaluated candidate decisions\n\n"
    for r in results:
        text += f"- {r['market']} / {r['variant']} / {r['strategy']}, as of {r['asof']}: {r['decision_counts']}\n"
    (out/"summary.md").write_text(text,encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
