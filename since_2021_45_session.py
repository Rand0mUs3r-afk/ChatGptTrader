"""2021-onward, any eligible trading-session entries, maximum 45 sessions. No orders."""
import builtins
import json
from pathlib import Path
import numpy as np
import pandas as pd
import year_2026_45_session as base

START = pd.Timestamp("2021-01-01")
END = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()+pd.Timedelta(days=1)
OUTPUT = Path("reports/since_2021_45_session")


def output_path(value):
    return OUTPUT if str(value)=="reports/year_2026_45_session" else Path(value)


def progress(*args,**kwargs):
    if args and isinstance(args[0],str) and args[0].startswith("# 2026 year-to-date entries"):
        return
    builtins.print(*args,**kwargs)


simulate = base.configured_function(base.simulate,START=START,END=END)
load_market = base.configured_function(base.load_market,START=START,END=END)
run_base = base.configured_function(base.main,START=START,END=END,simulate=simulate,
    load_market=load_market,Path=output_path,print=progress)


def calendar_year_rows(daily,journal,summary):
    previous = float(summary["starting_equity"])
    result = []
    values = daily.assign(year=pd.to_datetime(daily["date"]).dt.year)
    for year,group in values.groupby("year",sort=True):
        curve = np.r_[previous,group.marked_equity.to_numpy(dtype=float)]
        peak = np.maximum.accumulate(curve)
        ending = float(curve[-1])
        closed = [t for t in journal if t["closed"] and int(t["exit_date"][:4])==year]
        result.append(dict(market=summary["market"],currency=summary["currency"],variant=summary["variant"],strategy=summary["strategy"],
            year=int(year),first_session=str(group.date.iloc[0]),last_session=str(group.date.iloc[-1]),
            starting_marked_equity=previous,ending_marked_equity=ending,marked_pnl=ending-previous,
            return_pct=100*(ending/previous-1),within_year_drawdown_pct=float(100*np.max((peak-curve)/peak)),
            entries=sum(int(t["entry_date"][:4])==year for t in journal),closed_trades=len(closed),
            wins=sum(t["net_pnl"]>0 for t in closed),losses=sum(t["net_pnl"]<0 for t in closed)))
        previous = ending
    return result


def main():
    from swingbot.scanner import load_tickers
    if {"AMD","AMZN"} & set(load_tickers("config/tickers.txt")):
        raise ValueError("AMD or AMZN unexpectedly present in source watchlist")
    run_base()
    path = OUTPUT/"results.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if report["entry_start"]!=str(START.date()):
        raise ValueError("Entry-window configuration mismatch")
    notes = ("2021-ONWARD RESEARCH, entries from January 1, 2021 through the latest completed exchange "
        "session available at execution. Any eligible trading session may supply an entry when prior-close "
        "strategy rules pass; there is no Monday, month, anniversary or October-only restriction. This "
        "does not force a trade every day. Maximum 45 TRADING SESSIONS, entry is session one; SL/TP may "
        "exit earlier. One position at a time per independent scenario, no same-day reentry. Accounts "
        "compound across calendar years; positions carry across year boundaries. Calendar-year returns "
        "use marked equity, not reset accounts; the final year may be incomplete. Only pre-entry signals "
        "and matured outcomes inform decisions. Request ten years of pre-2021 history from 2011, retain "
        "all available requested bars, and disclose actual coverage and sample feasibility. Preserve "
        "20 calibration/10 qualifying walk-forward minimums, positive-edge checks, 30-example training "
        "window, raw-R target grid and original pattern stops. Insufficient evidence is not a trade. "
        "Use the current source watchlist without AMD or AMZN; this is a retrospective full-period "
        "cohort study, not a reconstructed point-in-time historical universe. The inherited loader "
        "requires at least 60 pre-January-2021 sessions; later-listed names failing that criterion "
        "are excluded from the whole study and listed in universe exclusions, not padded with invented "
        "prices. Known later TSX selections retain recorded eligibility dates, not January 2021. "
        "Compression/balanced/trend-family signals, empirical targets and labeled fixed-2R controls. "
        "Separate USD/CAD accounts, fractional sizing by default, 25% allocation and 1.5% planned "
        "equity-risk caps, 15 bps/side, zero commissions/dividend cash; gaps may exceed planned risk. "
        "Daily stop-first fills, broker fractional execution unverified, current-universe and "
        "development-sample bias; historical hit rates are not forecast probabilities. Open positions "
        "remain marked and unclassified as wins/losses. Zero-entry scenarios are not evaluable. "
        "Do not sum independent scenarios as a portfolio. Previous October and 2026-YTD outputs "
        "remain untouched. No orders or live strategy promotion.")
    annual = []
    for summary in report["results"]:
        directory = OUTPUT/summary["market"]/summary["variant"]
        stem = summary["strategy"]+"_h45"
        daily = pd.read_csv(directory/f"{stem}_daily_equity.csv")
        journal = json.loads((directory/f"{stem}_journal.json").read_text(encoding="utf-8"))
        annual.extend(calendar_year_rows(daily,journal,summary))
    report.update(experiment="since_2021_45_session_empirical_targets",notes=notes,
        entry_schedule="any_eligible_trading_session_with_qualifying_signal",excluded_us_tickers=["AMD","AMZN"],
        calibration_requested_start="2011-01-01",calendar_year_results=annual)
    path.write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    yearly = pd.DataFrame(annual)
    yearly.to_csv(OUTPUT/"calendar_year_results.csv",index=False)
    summaries = pd.DataFrame(report["results"])
    fields = ["market","variant","strategy","asof","entries","closed_trades","wins","losses","open_positions","ending_marked_equity","total_return_pct","max_marked_drawdown_pct","activity_status"]
    text = "# Entries since 2021 - maximum 45 trading sessions\n\n"+notes+"\n\n## Full-period results\n\n```text\n"+summaries[fields].to_string(index=False)+"\n```\n"
    text += "\n## Calendar-year results (continuous accounts, no annual reset)\n\n```text\n"+yearly.to_string(index=False)+"\n```\n"
    previous = (OUTPUT/"summary.md").read_text(encoding="utf-8")
    marker = "## Pre-entry sample feasibility (not trade approval)"
    if marker in previous:
        text += "\n"+marker+previous.split(marker,1)[1]
    (OUTPUT/"summary.md").write_text(text,encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
