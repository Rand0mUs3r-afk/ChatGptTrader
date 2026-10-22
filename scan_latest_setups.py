"""Latest completed-session research scan. Never submits orders."""
import argparse
import json
import math
import os
from pathlib import Path
import pandas as pd

MODES = ("compression_family", "balanced_blend")


def session_window(calendar, now):
    now = pd.Timestamp(now)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware run time required")
    day = now.tz_convert("America/New_York").date()
    sessions = calendar.sessions_in_range(pd.Timestamp(day)-pd.Timedelta(days=90),
                                          pd.Timestamp(day)+pd.Timedelta(days=30))
    complete = [s for s in sessions if calendar.session_close(s)+pd.Timedelta(minutes=20) <= now]
    if len(complete) < 20:
        raise ValueError("Insufficient calendar coverage")
    signal = complete[-1]
    future = [s for s in sessions if s > signal]
    if len(future) < 7:
        raise ValueError("Insufficient future calendar coverage")
    if now >= calendar.session_open(future[0]):
        raise ValueError("Next entry session already opened; no actionable pre-open scan available")
    return complete[-20:], future


def price_plan(entry, stop, equity, bps=15):
    if not all(math.isfinite(x) and x > 0 for x in (entry, stop, equity)):
        raise ValueError("Prices and equity must be finite and positive")
    if bps not in (5, 15) or entry <= stop:
        raise ValueError("Invalid cost scenario or entry at/below stop")
    slip = bps / 10000
    fill = entry * (1 + slip)
    risk_per_share = fill - stop * (1 - slip)
    shares = min(math.floor(equity * 0.25 / fill),
                 math.floor(equity * 0.015 / risk_per_share))
    target = entry + 2 * (entry - stop)
    return dict(provisional_entry=entry, stop=stop, provisional_target=target,
                shares=shares, estimated_cost=shares*fill,
                planned_stop_risk=shares*risk_per_share,
                planned_target_profit=shares*(target*(1-slip)-fill),
                max_open_for_one_share=min(equity*0.25/(1+slip),
                    (equity*0.015+stop*(1-slip))/(1+slip)))


def main():
    import exchange_calendars as xcals
    import yfinance as yf
    from swingbot.scanner import load_tickers
    from run_recent_blend import FAMILIES, candidate, features, prepare

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--equity", type=float, default=1000.0)
    args = parser.parse_args()
    if not math.isfinite(args.equity) or args.equity <= 0:
        raise ValueError("Equity must be finite and positive")
    out = Path("reports/latest_setups")
    out.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="UTC")
    expected, future = session_window(xcals.get_calendar("XNYS"), now)
    signal_date = pd.Timestamp(expected[-1]).tz_localize(None).normalize()
    cutoff = signal_date + pd.Timedelta(days=1)
    tickers = sorted(set(load_tickers("config/tickers.txt")))
    if not tickers:
        raise ValueError("Empty ticker universe")
    data = {}
    coverage = {}
    for ticker in tickers:
        raw = yf.Ticker(ticker).history(
            start=str((cutoff-pd.DateOffset(months=6)).date()),
            end=str(cutoff.date()), interval="1d", auto_adjust=True,
            actions=False, raise_errors=True)
        frame = prepare(raw, cutoff)
        required = pd.DatetimeIndex(expected).tz_localize(None).normalize()
        if len(frame) < 20 or not frame.index[-20:].equals(required):
            raise ValueError(f"{ticker}: missing/stale sessions; refusing partial-universe scan")
        frame.to_csv(out / f"bars_{ticker}.csv", index_label="Date")
        data[ticker] = features(frame)[-1]
        coverage[ticker] = dict(bars=len(frame), latest=str(frame.index[-1].date()))
    weights = {family: 1/len(FAMILIES) for family in FAMILIES}
    rows = []
    for mode in MODES:
        candidates = []
        for ticker, feature in data.items():
            signal = candidate(feature, mode, weights, False)
            if signal is not None:
                candidates.append((-signal["score"],
                    -feature["quality"] if mode == "balanced_blend" else 0,
                    ticker, signal))
        rank = 0
        for _, _, ticker, signal in sorted(candidates, key=lambda x: x[:3]):
            plan = price_plan(data[ticker]["close"], signal["stop"], args.equity)
            eligible = plan["shares"] > 0
            if eligible:
                rank += 1
            for hold in (5, 7):
                rows.append(dict(strategy=mode, ticker=ticker, max_hold_sessions=hold,
                    signal_date=str(signal_date.date()),
                    conditional_entry_date=str(pd.Timestamp(future[0]).date()),
                    latest_exit_date=str(pd.Timestamp(future[hold-1]).date()),
                    provisional_rank=rank if eligible else None,
                    eligible_at_reference_price=eligible,
                    votes=", ".join(signal["votes"]),
                    families=", ".join(signal["groups"]), **plan))
    report = dict(status="ok", generated_at=str(now), signal_date=str(signal_date.date()),
        equity=args.equity, allocation_cap_pct=25, planned_risk_cap=args.equity*0.015,
        bps_per_side=15, coverage=coverage, setups=rows,
        entry_basis="Signal close is a placeholder, NOT an executable entry quote",
        position_rule="Each strategy/holding period is a separate scenario; one position only, no pyramiding",
        expiry="Only valid before the conditional entry session opens; rerun sizing using actual opening price",
        scalping="DISABLED; daily bars only")
    (out / "setups.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    columns = ["strategy", "ticker", "max_hold_sessions", "signal_date", "conditional_entry_date",
        "latest_exit_date", "provisional_rank", "eligible_at_reference_price", "votes", "families",
        "provisional_entry", "stop", "provisional_target", "shares", "estimated_cost",
        "planned_stop_risk", "planned_target_profit", "max_open_for_one_share"]
    pd.DataFrame(rows, columns=columns).to_csv(out / "setups.csv", index=False)
    text = f"# Latest setup scan\n\nSignal session: {signal_date.date()}; generated: {now}.\n\n"
    text += ("Research only; no orders. Entry, target, quantity, cost and risk are PROVISIONAL at the signal close. "
        "At the next opening price, require open > stop, recompute target = open + 2*(open-stop), "
        "and rerun share sizing with 15 bps per side. Skip zero-share entries. "
        "Gap losses can exceed planned stop risk. Exit on stop/target first, otherwise at the listed session close. "
        "Dates use XNYS holidays and count entry as session one.\n\n"
        "Each strategy/holding limit is a separate scenario, not simultaneous allocations. "
        "Rank 1 is the first affordable candidate at the reference price; rank may change at the open. "
        "Existing holdings and available cash are NOT checked; this assumes a flat account. "
        "Scalping is disabled.\n\n")
    text += "| Strategy | Ticker | Hold | Rank | Entry date | Exit deadline | Ref entry | SL | Ref TP | Shares | Risk | Reward |\n"
    text += "|---|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|\n"
    for r in rows:
        text += (f"| {r['strategy']} | {r['ticker']} | {r['max_hold_sessions']} | {r['provisional_rank'] or '-'} "
            f"| {r['conditional_entry_date']} | {r['latest_exit_date']} | {r['provisional_entry']:.2f} "
            f"| {r['stop']:.2f} | {r['provisional_target']:.2f} | {r['shares']} "
            f"| {r['planned_stop_risk']:.2f} | {r['planned_target_profit']:.2f} |\n")
    if not rows:
        text += "\nNo qualifying setups. Cash/no trade is a valid result.\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        output = Path("reports/latest_setups")
        output.mkdir(parents=True, exist_ok=True)
        for stale in ("setups.json", "setups.csv", "summary.md"):
            (output/stale).unlink(missing_ok=True)
        (output/"error.txt").write_text(f"SCAN FAILED; no actionable report: {type(exc).__name__}: {exc}\n", encoding="utf-8")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as handle:
                handle.write("# Setup scan failed\nNo actionable report. See error.txt and job logs.\n")
        raise
