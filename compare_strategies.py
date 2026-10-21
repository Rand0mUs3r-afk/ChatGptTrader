"""Fixed-rule comparison with full accepted-trade journals and manual execution."""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from swingbot.backtest import simulate_trade, summarize_trades
from swingbot.config import DEFAULT_SETTINGS
from swingbot.data import fetch_history
from swingbot.experimental import generate_trend_pullback, select_signals
from swingbot.indicators import calculate_features
from swingbot.journal import build_journal
from swingbot.journal_report import capture_trade, enrich_journal, render_journal
from swingbot.scanner import load_tickers
from swingbot.strategies import generate_signals

MODES = ("baseline", "experimental", "blend")


def main():
    settings = DEFAULT_SETTINGS
    output = Path("reports/strategy_experiment")
    output.mkdir(parents=True, exist_ok=True)
    symbols = list(dict.fromkeys([settings.benchmark] + load_tickers("config/tickers.txt")))
    panel, hashes = {}, {}
    for ticker in symbols:
        bars = fetch_history(ticker, settings).copy()
        bars.index = pd.DatetimeIndex(bars.index).tz_localize(None).normalize()
        if bars.index.has_duplicates:
            raise ValueError(f"Duplicate sessions for {ticker}")
        panel[ticker] = bars
        snapshot = bars.to_csv(index_label="Date")
        name = "".join(c if c.isalnum() or c in "._-" else "_" for c in ticker)
        (output / f"{name}.csv").write_text(snapshot, encoding="utf-8")
        hashes[ticker] = hashlib.sha256(snapshot.encode()).hexdigest()
    benchmark = panel[settings.benchmark]
    market_features = calculate_features(benchmark, settings=settings)
    features, dates = {}, None
    for ticker, bars in panel.items():
        if ticker == settings.benchmark:
            continue
        features[ticker] = calculate_features(bars, benchmark["Close"], settings)
        eligible = bars.index[settings.minimum_history - 1:len(bars) - settings.maximum_holding_days]
        dates = eligible if dates is None else dates.intersection(eligible)
    if dates is None:
        raise ValueError("No non-benchmark tickers configured.")
    dates = dates.intersection(benchmark.index).sort_values()
    if len(dates) < 10:
        raise ValueError("Insufficient shared dates after warmup and full-hold exclusion.")
    split = dates[int(len(dates) * 0.8)]
    observations = {mode: [] for mode in MODES}
    for ticker, frame in features.items():
        bars = panel[ticker]
        for date in dates:
            index = bars.index.get_loc(date)
            history = frame.iloc[:index + 1]
            market = market_features.loc[date]
            market_ok = bool(market["Close"] > market["EMA20"] > market["SMA50"])
            baseline = generate_signals(ticker, history, settings, benchmark_uptrend=market_ok)
            experimental = generate_trend_pullback(ticker, history, settings, market_ok)
            for mode in MODES:
                for signal in select_signals(baseline, experimental, mode):
                    trade = simulate_trade(bars, index, signal, settings)
                    if trade is None:
                        continue
                    trade = capture_trade(trade, signal, history, market_ok, mode)
                    if pd.Timestamp(trade["signal_date"]) >= split:
                        trade["partition"] = "holdout"
                    elif pd.Timestamp(trade["exit_date"]) < split:
                        trade["partition"] = "development"
                    else:
                        trade["partition"] = "boundary"
                    observations[mode].append(trade)
    results, sections = [], []
    for mode, rows in observations.items():
        candidates = pd.DataFrame(rows)
        candidates.to_csv(output / f"{mode}_candidates.csv", index=False)
        for partition in ("full", "development", "holdout"):
            sample = candidates.copy() if partition == "full" or not rows else candidates[candidates["partition"] == partition].copy()
            journal, account = build_journal(sample, settings)
            journal, account = enrich_journal(journal, account, sample)
            journal.to_csv(output / f"{mode}_{partition}_journal.csv", index=False)
            title = f"{mode} / {partition}"
            (output / f"{mode}_{partition}_journal.md").write_text(render_journal(journal, account, title), encoding="utf-8")
            sections.append(render_journal(journal, account, title, include_trades=False))
            result = {k: v for k, v in account.items() if k != "mode"}
            result.update(mode=mode, partition=partition,
                          independent_candidate_statistics=summarize_trades(sample))
            results.append(result)
    note = ("Each mode and partition is a separate replay with reset equity; do not sum them. "
            "Full includes boundary trades; development/holdout exclude crossing trades. "
            "Single position, no exit-day reentry, closed-trade drawdown rather than daily MTM. "
            "Current universe has survivorship bias; no earnings/opening-gap revalidation. "
            "Repeated holdout tuning invalidates independent validation. Not actual orders.")
    manifest = dict(settings=asdict(settings), snapshot_sha256=hashes, results=results, note=note,
                    first_signal_date=str(dates[0].date()), last_signal_date=str(dates[-1].date()),
                    chronological_holdout_start=str(split.date()))
    (output / "comparison.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    text = "# Strategy trading journals\n\n" + note + "\n\n" + "\n".join(sections)
    text += "\nTrade-by-trade reasons and indicator snapshots are in the *_journal.md and CSV files in the strategy-comparison artifact.\n"
    (output / "comparison.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
