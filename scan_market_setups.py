"""Separate US/USD and TSX/CAD research scans; never submits orders."""
import argparse
import json
import math
import os
from pathlib import Path
import pandas as pd
from scan_latest_setups import price_plan, session_window

MARKETS = {
    "us": ("config/tickers.txt", "XNYS", "USD"),
    "tsx": ("config/tickers_tsx.txt", "XTSE", "CAD"),
}


def market_settings(market):
    if market not in MARKETS:
        raise ValueError("Choose us or tsx")
    return MARKETS[market]


def main():
    import exchange_calendars as xcals
    import yfinance as yf
    from swingbot.scanner import load_tickers
    from run_recent_blend import FAMILIES, candidate, features, prepare
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", choices=MARKETS, required=True)
    parser.add_argument("--equity", type=float, required=True,
        help="Equity in selected market currency: USD for us, CAD for tsx; no FX conversion")
    args = parser.parse_args()
    if not math.isfinite(args.equity) or args.equity <= 0:
        raise ValueError("Equity must be finite and positive")
    ticker_file, calendar_name, currency = market_settings(args.market)
    out = Path("reports/latest_setups")
    out.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz="UTC")
    expected, future = session_window(xcals.get_calendar(calendar_name), now)
    required = pd.DatetimeIndex(expected).tz_localize(None).normalize()
    signal_date = required[-1]
    cutoff = signal_date + pd.Timedelta(days=1)
    tickers = sorted(set(load_tickers(ticker_file)))
    if not tickers or (args.market == "tsx" and any(not t.endswith(".TO") for t in tickers)):
        raise ValueError("Empty or invalid market watchlist")
    data, coverage = {}, {}
    for ticker in tickers:
        raw = yf.Ticker(ticker).history(
            start=str((cutoff-pd.DateOffset(months=6)).date()), end=str(cutoff.date()),
            interval="1d", auto_adjust=True, actions=False, raise_errors=True)
        frame = prepare(raw, cutoff)
        if len(frame) < 20 or not frame.index[-20:].equals(required):
            raise ValueError(f"{ticker}: missing/stale sessions; no partial-universe scan")
        frame.to_csv(out/f"bars_{ticker}.csv", index_label="Date")
        data[ticker] = features(frame)[-1]
        coverage[ticker] = dict(bars=len(frame), latest=str(frame.index[-1].date()))
    rows = []
    weights = {family: 1/len(FAMILIES) for family in FAMILIES}
    for mode in ("compression_family", "balanced_blend"):
        candidates = []
        for ticker, feature in data.items():
            signal = candidate(feature, mode, weights, False)
            if signal:
                quality = -feature["quality"] if mode == "balanced_blend" else 0
                candidates.append((-signal["score"], quality, ticker, signal))
        rank = 0
        for _, _, ticker, signal in sorted(candidates, key=lambda x: x[:3]):
            plan = price_plan(data[ticker]["close"], signal["stop"], args.equity)
            if plan["shares"] > 0:
                rank += 1
            for hold in (5, 7):
                rows.append(dict(market=args.market, currency=currency, strategy=mode,
                    ticker=ticker, max_hold_sessions=hold, signal_date=str(signal_date.date()),
                    conditional_entry_date=str(pd.Timestamp(future[0]).date()),
                    latest_exit_date=str(pd.Timestamp(future[hold-1]).date()),
                    provisional_rank=rank if plan["shares"] > 0 else None,
                    eligible_at_reference_price=plan["shares"] > 0,
                    votes=", ".join(signal["votes"]), families=", ".join(signal["groups"]), **plan))
    notes = ("Research only; NO ORDERS. All monetary values and entered equity are in " + currency + ". "
        "No FX conversion or shared US/Canada portfolio budgeting. Each strategy/holding period is a separate "
        "one-position scenario, assuming a flat account; existing holdings and available cash are not checked. "
        "Entry, TP, quantity and risk are PROVISIONAL at the signal close, not executable quotes. "
        "Before entering, require actual open > SL, recompute TP = open + 2*(open-SL), and rerun sizing. "
        "Allocation cap 25%; planned stop-risk ceiling 1.5% of equity; 15 bps per side. "
        "Skip zero-share candidates. Gaps can exceed planned risk. Rank 1 is first affordable at the reference "
        "price; ranks may change at the open. Stop/target exits take priority over the time limit; if both "
        "are touched within one daily bar, research assumes stop first. Exit deadline counts entry as session one "
        "using the selected exchange calendar. Report expires at the next entry-session open. Scalping disabled.")
    report = dict(status="ok", generated_at=str(now), market=args.market, calendar=calendar_name,
        currency=currency, equity=args.equity, planned_risk_cap=args.equity*0.015,
        signal_date=str(signal_date.date()), coverage=coverage, notes=notes, setups=rows)
    (out/"setups.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    columns = ["market", "currency", "strategy", "ticker", "max_hold_sessions", "signal_date",
        "conditional_entry_date", "latest_exit_date", "provisional_rank", "eligible_at_reference_price",
        "votes", "families", "provisional_entry", "stop", "provisional_target", "shares",
        "estimated_cost", "planned_stop_risk", "planned_target_profit", "max_open_for_one_share"]
    pd.DataFrame(rows, columns=columns).to_csv(out/"setups.csv", index=False)
    text = f"# Latest {args.market.upper()} setups ({currency})\n\nSignal: {signal_date.date()}; generated: {now}.\n\n{notes}\n\n"
    text += "| Strategy | Ticker | Hold | Rank | Entry date | Exit deadline | Ref entry | SL | Ref TP | Shares | Risk | Reward |\n"
    text += "|---|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|\n"
    for r in rows:
        text += (f"| {r['strategy']} | {r['ticker']} | {r['max_hold_sessions']} | {r['provisional_rank'] or '-'} "
            f"| {r['conditional_entry_date']} | {r['latest_exit_date']} | {r['provisional_entry']:.2f} "
            f"| {r['stop']:.2f} | {r['provisional_target']:.2f} | {r['shares']} "
            f"| {r['planned_stop_risk']:.2f} | {r['planned_target_profit']:.2f} |\n")
    if not rows:
        text += "\nNo qualifying setups. Cash/no trade is valid.\n"
    (out/"summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        out = Path("reports/latest_setups")
        out.mkdir(parents=True, exist_ok=True)
        for stale in ("setups.json", "setups.csv", "summary.md"):
            (out/stale).unlink(missing_ok=True)
        (out/"error.txt").write_text(f"SCAN FAILED; no actionable report: {type(exc).__name__}: {exc}\n", encoding="utf-8")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
                handle.write("# Setup scan failed\nNo actionable report. See logs and error.txt.\n")
        raise
