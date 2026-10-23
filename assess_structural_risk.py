"""Experimental joint structural SL/TP assessment; no orders."""
import json
import math
import runpy
from pathlib import Path
import numpy as np
import pandas as pd


def structural_stop(bars, mode):
    if mode not in ("compression_family","balanced_blend") or len(bars) < 15:
        raise ValueError("Unsupported mode or insufficient stop history")
    entry = float(bars.Close.iloc[-1])
    previous = bars.Close.shift()
    tr = pd.concat([bars.High-bars.Low,(bars.High-previous).abs(),(bars.Low-previous).abs()],axis=1).max(axis=1)
    atr = float(tr.iloc[-14:].mean())
    lows = bars.Low.to_numpy(dtype=float)
    pivots = [lows[j] for j in range(max(2,len(lows)-60),len(lows)-2)
        if lows[j] < min(lows[j-2:j]) and lows[j] < min(lows[j+1:j+3]) and lows[j] < entry]
    support = max(pivots) if pivots else None
    pattern_low = float(bars.Low.iloc[-(2 if mode == "compression_family" else 3):].min())
    anchor = min(pattern_low,support) if support is not None else pattern_low
    stop = min(anchor-0.25*atr,entry-1.5*atr)
    if not all(math.isfinite(x) for x in (entry,atr,stop)) or atr <= 0 or not 0 < stop < entry:
        raise ValueError("No valid structural stop")
    reason = (f"Pattern low {pattern_low:.4f}; nearest confirmed support {support}; "
        f"14-session simple ATR {atr:.4f}. Stop is below the lower structure anchor by 0.25 ATR, "
        "and no closer than 1.5 ATR below the signal close. These are experimental fixed rules, "
        "not optimized settings or proof that normal fluctuations cannot hit the stop.")
    return dict(stop=float(stop),stop_atr14=atr,pattern_low=pattern_low,
        nearest_confirmed_support=float(support) if support is not None else None,
        stop_buffer_atr=0.25,minimum_distance_atr=1.5,stop_reason=reason)


def risk_features(bars, mode, base_features=None):
    if base_features is None:
        from run_recent_blend import features
        base_features = features(bars)
    result = []
    for i,feature in enumerate(base_features):
        updated = feature.copy()
        try:
            stop = structural_stop(bars.iloc[:i+1],mode)["stop"]
            updated["stops"] = {vote:stop for vote in feature["active"]}
        except ValueError:
            updated.update(active=set(),stops={},groups=())
        result.append(updated)
    return result


def upgrade_risk(output="reports/latest_setups"):
    from assess_targets import assess, SLIP
    from scan_latest_setups import price_plan
    from run_recent_blend import prepare
    out = Path(output)
    report = json.loads((out/"setups.json").read_text(encoding="utf-8"))
    if report.get("status") != "ok":
        raise ValueError("Unsuccessful base scan")
    for name in ("setups.json","setups.csv","summary.md","target_audit.json"):
        (out/("pre_structural_"+name)).write_bytes((out/name).read_bytes())
    cached, audits = {}, {}
    cutoff = pd.Timestamp(report["signal_date"])+pd.Timedelta(days=1)
    for row in report["setups"]:
        ticker,mode = row["ticker"],row["strategy"]
        row.update(original_stop=row["stop"],original_shares=row["shares"],
            original_assessed_target=row["provisional_target"],original_net_rr=row.get("assessed_net_rr"),
            original_reference_2r_target=row["reference_2r_target"])
        row.update(historical_examples=None,walkforward_examples=None,walkforward_mean_net_r=None,
            walkforward_target_hit_pct=None,historical_median_mfe_r=None,nearest_confirmed_high=None)
        if "target_error" in row:
            row["prior_target_error"] = row.pop("target_error")
        try:
            key = (ticker,mode)
            if key not in cached:
                bars = prepare(pd.read_csv(out/f"target_history_{ticker}.csv",index_col="Date",parse_dates=True),cutoff)
                if str(bars.index[-1].date()) != report["signal_date"]:
                    raise ValueError("Stop history is stale")
                cached[key] = (bars,risk_features(bars,mode))
            bars,features = cached[key]
            row.update(structural_stop(bars,mode))
            row.update(price_plan(float(row["provisional_entry"]),row["stop"],float(report["equity"])))
            row["reference_2r_target"] = row["provisional_target"]
            check,audit = assess(bars,row,features)
            row.update(check)
            row["provisional_target"] = row["assessed_target"]
            row["planned_target_profit"] = (row["shares"]*(row["assessed_target"]*(1-SLIP)-
                row["provisional_entry"]*(1+SLIP))) if row["assessed_target"] is not None else None
            if row["shares"] == 0 and row["target_status"] == "EXPERIMENTAL_CANDIDATE":
                row["target_status"] = "SKIP_UNAFFORDABLE"
            audits[f"{ticker}_{mode}_h{row['max_hold_sessions']}"] = audit
            row["ranking_score"] = len([g for g in row["families"].split(",") if g.strip()])/3 if mode == "balanced_blend" else 1.0
            row["ranking_close_quality"] = float(features[-1]["quality"]) if mode == "balanced_blend" else 0.0
        except Exception as exc:
            row.update(target_status="RISK_DATA_ERROR",stop=None,assessed_target=None,provisional_target=None,
                assessed_net_rr=None,reference_2r_target=None,max_open_for_one_share=None,shares=0,estimated_cost=None,planned_stop_risk=None,planned_target_profit=None,
                risk_error=f"{type(exc).__name__}: {exc}")
        row["eligible_at_reference_price"] = row["shares"] > 0 and row["target_status"] == "EXPERIMENTAL_CANDIDATE"
        row["provisional_rank"] = None
        row["downside_scenario"] = (f"Structural SL: {row['stop']}. Do not enter at/below SL; "
            "after entry, stop exit applies. Gaps can exceed planned loss. " + row.get("stop_reason",row.get("risk_error","")))
        row["upside_scenario"] = (f"Reassessed TP: {row['assessed_target']}; net RR: {row['assessed_net_rr']}; "
            f"status: {row['target_status']}. Targets and historical outcomes use the new stop model; no price guarantee.")
    for mode in ("compression_family","balanced_blend"):
        for hold in (5,7):
            group = sorted([r for r in report["setups"] if r["strategy"] == mode and r["max_hold_sessions"] == hold
                and r["eligible_at_reference_price"]],key=lambda r:(-r["ranking_score"],-r["ranking_close_quality"],r["ticker"]))
            for rank,row in enumerate(group,1):
                row["provisional_rank"] = rank
    method = ("EXPERIMENTAL JOINT SL/TP RESEARCH; no orders. Uses confirmed five-bar swing lows from the last "
        "60 sessions and the last two bars' pattern low for compression, or three bars for balanced blend. "
        "SL is the lower structure anchor minus 0.25 simple ATR(14), with minimum distance 1.5 ATR below signal close. "
        "Confirmed lows require two completed bars on each side; historical features use only then-known bars. "
        "Signal qualification is unchanged. Historical excursions, targets and walk-forward results are recalculated "
        "using the SAME new stop rule, separately for five/seven sessions. TP is capped by the median historical "
        "favorable excursion under that stop and the nearest confirmed swing high minus 0.1 ATR. At least 20 "
        "past examples, 10 qualifying walk-forward examples, positive mean net R and net RR >= 1.25 are required. Shares are recalculated with 25% allocation cap and 1.5% equity planned-risk cap, with "
        "15 bps/side. Never tighten SL just to improve RR; a wider stop can reduce shares or cause a skip. "
        "Parameters are disclosed research choices, not validated optimal values. Daily stop-first/gap assumptions, "
        "price-basis and missing-data safeguards remain. No news/earnings checks or calibrated forecast probabilities. "
        "Levels and quantities are provisional; reassess at actual entry. Earlier results are preserved in pre_structural files.")
    report["prior_target_method"] = report.get("target_method")
    report["target_method"] = method
    report["stop_method"] = method
    report["prior_notes"] = report.get("notes")
    report["notes"] = method
    (out/"structural_risk_audit.json").write_text(json.dumps(audits,indent=2,allow_nan=False),encoding="utf-8")
    (out/"setups.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    if report["setups"]:
        pd.DataFrame(report["setups"]).to_csv(out/"setups.csv",index=False)
    fmt = lambda v:"N/A" if v is None else f"{float(v):.2f}"
    text = f"# Joint structural SL and TP ({report['market'].upper()}, {report['currency']})\n\n{method}\n\n"
    text += "| Ticker | Strategy | Hold | Status | Entry ref | Old SL | New SL | Assessed TP | Net RR | Shares | Planned loss | Planned profit |\n"
    text += "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for r in report["setups"]:
        text += (f"| {r['ticker']} | {r['strategy']} | {r['max_hold_sessions']} | {r['target_status']} "
            f"| {fmt(r['provisional_entry'])} | {fmt(r['original_stop'])} | {fmt(r['stop'])} "
            f"| {fmt(r['assessed_target'])} | {fmt(r['assessed_net_rr'])} | {r['shares']} "
            f"| {fmt(r['planned_stop_risk'])} | {fmt(r['planned_target_profit'])} |\n")
    if not report["setups"]:
        text += "\nNo qualifying base setups; no SL/TP invented.\n"
    for r in report["setups"]:
        text += f"\n## {r['ticker']} / {r['strategy']} / {r['max_hold_sessions']} sessions\n\n"
        for key in ("why_rules","price_evidence","stop_reason","downside_scenario","upside_scenario","time_exit_scenario","risk_error"):
            if key in r:
                text += f"- {key.replace('_',' ').capitalize()}: {r[key]}\n"
        text += f"- Historical examples: {r.get('historical_examples','N/A')}; walk-forward examples: {r.get('walkforward_examples','N/A')}; mean net R: {fmt(r.get('walkforward_mean_net_r'))}.\n"
        text += f"- Conditional entry: {r['conditional_entry_date']}; exit deadline: {r['latest_exit_date']}; eligible: {r['eligible_at_reference_price']}.\n"
    (out/"summary.md").write_text(text,encoding="utf-8")
    print(text)


if __name__ == "__main__":
    runpy.run_module("assess_targets",run_name="__main__")
    upgrade_risk()
