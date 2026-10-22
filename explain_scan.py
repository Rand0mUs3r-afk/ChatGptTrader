"""Explain deterministic scan decisions and conditional scenarios, not forecasts."""
import json
import runpy
from pathlib import Path
import pandas as pd

RULES = {
    "breakout3": "Bullish candle closed above the previous three sessions' highs.",
    "momentum3": "Bullish candle and two consecutive close-to-close rises.",
    "reversal2": "Previous candle was bearish; the bullish signal candle closed above its high.",
    "dip_rebound3": "Previous close was below the prior-three-close mean minus one population standard deviation; the bullish signal closed higher.",
    "inside_breakout": "Previous candle was strictly inside its predecessor; the bullish signal closed above the inside candle's high.",
    "failed_reclaim": "Price undercut the previous three-session low, reclaimed it, and closed bullish in the top quarter of its range.",
    "compression_breakout": "Previous range was narrower than each of the two preceding ranges; the bullish signal closed above the previous high.",
    "fast_breakout": "Bullish signal candle closed above the previous session's high.",
    "fast_reversal": "Previous candle was bearish; the bullish signal closed above its high.",
    "fast_momentum": "Bullish candle closed above the previous close.",
    "bullish_engulfing": "Bullish body engulfed the previous bearish body, allowing equal body boundaries.",
}


def explain_row(row, bars):
    if len(bars) < 4 or str(pd.Timestamp(bars.index[-1]).date()) != row["signal_date"]:
        raise ValueError("Explanation snapshot does not match signal session")
    votes = [v.strip() for v in row["votes"].split(",") if v.strip()]
    if not votes or any(v not in RULES for v in votes):
        raise ValueError("Unknown or missing strategy rule; refusing an invented explanation")
    last = bars.iloc[-1]
    span = float(last.High-last.Low)
    quality = float((last.Close-last.Low)/span) if span > 0 else 0.0
    currency = row["currency"]
    price = lambda value: f"{currency} {float(value):.2f}"
    reasons = " ".join(f"{vote}: {RULES[vote]}" for vote in votes)
    evidence = (f"Signal OHLC: {price(last.Open)} / {price(last.High)} / {price(last.Low)} / {price(last.Close)}. "
        f"Previous high: {price(bars.High.iloc[-2])}; previous three-session high: {price(bars.High.iloc[-4:-1].max())}. "
        f"Close location: {quality*100:.1f}% up the signal day's range. Higher close location is a ranking "
        "tie-breaker for balanced blend, not a win probability.")
    if row["strategy"] == "balanced_blend":
        selection = (f"At least two signal families agreed ({row['families']}). Equal family weights rank "
            "three-family agreement above two-family agreement; ties use close location, then ticker alphabetically.")
    elif row["strategy"] == "compression_family":
        selection = ("At least one compression-family rule fired. This strategy assigns equal candidate scores "
            "and orders candidates alphabetically; rank 1 does NOT mean the strongest or most likely winner.")
    else:
        raise ValueError("Unsupported ranking rule")
    if row["eligible_at_reference_price"]:
        selection += f" Provisional affordable rank: {row['provisional_rank']}; quantity: {row['shares']} shares."
    else:
        selection += " Watchlist signal only: zero shares fit the allocation/risk caps at the reference price."
    stop, entry, target = (float(row[k]) for k in ("stop", "provisional_entry", "provisional_target"))
    thesis = ("Conditional bullish continuation/recovery hypothesis, not a forecast: if the next open is above "
        f"{price(stop)} and quantity remains affordable, the strategy looks for upside from the actual entry "
        "while its fixed stop remains intact. It does not predict the order of future daily moves.")
    upside = (f"Reference entry {price(entry)} gives a provisional target of {price(target)}. "
        "Target = actual opening price + 2*(actual opening price - stop); recalculate at entry. "
        "This is a two-times-price-risk exit rule before costs, NOT a fair-value estimate or expected price.")
    downside = (f"A next-session open at/below {price(stop)} invalidates entry. After entry, touching the stop "
        "triggers exit under the strategy; a gap through it can lose more than planned. The stop is the minimum "
        "of the fired rules' stop levels, not a verified floor that price must respect.")
    timeout = (f"If neither stop nor target exits first, close by {row['latest_exit_date']} "
        f"(maximum {row['max_hold_sessions']} exchange sessions, counting entry as session one). "
        "A sideways path can therefore end in a small gain or loss rather than reaching either level.")
    return dict(why_rules=reasons, price_evidence=evidence, ranking_explanation=selection,
        conditional_thesis=thesis, upside_scenario=upside, downside_scenario=downside,
        time_exit_scenario=timeout, probability_note="Not estimated: no calibrated success probability or forecast model. "
        "These explanations use saved daily OHLCV and strategy rules only, not news, fundamentals or earnings checks.")


def enrich(output="reports/latest_setups"):
    out = Path(output)
    report = json.loads((out/"setups.json").read_text(encoding="utf-8"))
    if report.get("status") != "ok":
        raise ValueError("Cannot explain an unsuccessful scan")
    snapshots = {}
    text = "\n\n## Why these setups and how they could play out\n\n"
    text += "Scenarios, not predictions. Selection and sizing are unchanged. No orders are placed.\n\n"
    fields = []
    for row in report["setups"]:
        ticker = row["ticker"]
        if ticker not in snapshots:
            snapshots[ticker] = pd.read_csv(out/f"bars_{ticker}.csv", index_col="Date", parse_dates=True)
        explanation = explain_row(row, snapshots[ticker])
        row.update(explanation)
        fields = list(explanation)
        text += f"### {ticker} - {row['strategy']} - maximum {row['max_hold_sessions']} sessions\n\n"
        for key, value in explanation.items():
            text += f"- {key.replace('_', ' ').capitalize()}: {value}\n"
        text += "\n"
    if not report["setups"]:
        text += "No qualifying setups; no bullish thesis or price scenario was invented.\n"
    report["explanation_method"] = "Deterministic saved-data explanations; conditional scenarios, no forecast probabilities"
    summary = (out/"summary.md").read_text(encoding="utf-8")
    summary = summary.split("\n\n## Why these setups and how they could play out")[0] + text
    table = pd.read_csv(out/"setups.csv")
    for key in fields:
        table[key] = [row[key] for row in report["setups"]]
    (out/"setups.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    table.to_csv(out/"setups.csv", index=False)
    (out/"summary.md").write_text(summary, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    runpy.run_module("scan_market_setups", run_name="__main__")
    enrich()
