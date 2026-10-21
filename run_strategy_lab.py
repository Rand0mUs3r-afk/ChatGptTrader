"""Long-history hypothesis screening; no automated tuning or winner deployment."""
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from swingbot.backtest import simulate_trade
from swingbot.config import DEFAULT_SETTINGS
from swingbot.data import fetch_history
from swingbot.experimental import generate_trend_pullback
from swingbot.indicators import calculate_features
from swingbot.journal import build_journal
from swingbot.journal_report import capture_trade, enrich_journal, render_journal
from swingbot.refined import select_signals
from swingbot.scanner import load_tickers
from swingbot.strategies import generate_signals
from swingbot.strategy_lab import FAMILIES, add_features, generate_candidates

HOLDS = (5, 10, 20)
COSTS_BPS = (5.0, 15.0)
MODES = ("baseline", "experimental", "blend", "refined") + FAMILIES


def main():
    settings = replace(DEFAULT_SETTINGS, period="2y")
    output = Path("reports/strategy_lab")
    output.mkdir(parents=True, exist_ok=True)
    symbols = list(dict.fromkeys([settings.benchmark] + load_tickers("config/tickers.txt")))
    panel, coverage = {}, {}
    for ticker in symbols:
        bars = fetch_history(ticker, settings).copy().iloc[:-1]
        bars.index = pd.DatetimeIndex(bars.index).tz_localize(None).normalize()
        if len(bars) < settings.minimum_history or bars.index.has_duplicates:
            raise ValueError(f"Invalid or insufficient history: {ticker}")
        panel[ticker] = bars
        snapshot = bars.to_csv(index_label="Date")
        name = "".join(c if c.isalnum() or c in "._-" else "_" for c in ticker)
        (output / f"{name}.csv").write_text(snapshot, encoding="utf-8")
        coverage[ticker] = dict(start=str(bars.index[0].date()), end=str(bars.index[-1].date()),
                               bars=len(bars), sha256=hashlib.sha256(snapshot.encode()).hexdigest())
    benchmark = panel[settings.benchmark]
    common_end = min(bars.index[-1] for bars in panel.values())
    evaluation = benchmark.index[settings.minimum_history - 1:]
    evaluation = evaluation[evaluation <= common_end]
    if len(evaluation) < 100:
        raise ValueError("Insufficient benchmark evaluation history.")
    split = evaluation[int(len(evaluation) * 0.8)]
    market_features = calculate_features(benchmark, settings=settings)
    observations = {(mode, hold): [] for mode in MODES for hold in HOLDS}
    for ticker, bars in panel.items():
        if ticker == settings.benchmark:
            continue
        frame = add_features(calculate_features(bars, benchmark["Close"], settings))
        for index in range(settings.minimum_history - 1, len(bars) - max(HOLDS)):
            date = bars.index[index]
            if date not in evaluation or bars.index[index + max(HOLDS)] > common_end:
                continue
            history = frame.iloc[:index + 1]
            market = market_features.loc[date]
            market_ok = bool(market["Close"] > market["EMA20"] > market["SMA50"])
            baseline = generate_signals(ticker, history, settings, benchmark_uptrend=market_ok)
            experimental = generate_trend_pullback(ticker, history, settings, market_ok)
            signals = generate_candidates(ticker, history, settings)
            for mode in MODES[:4]:
                signals[mode] = select_signals(baseline, experimental, mode)
            for mode, candidates in signals.items():
                for signal in candidates:
                    for hold in HOLDS:
                        execution = replace(settings, maximum_holding_days=hold, slippage_bps=5.0)
                        trade = simulate_trade(bars, index, signal, execution)
                        if trade is None:
                            continue
                        trade = capture_trade(trade, signal, history, market_ok, mode)
                        trade["selection_policy"] = ("Fixed hypothesis; first eligible ticker alphabetically by entry date; "
                                                     "single position, no exit-day reentry, cash/risk caps apply.")
                        trade["partition"] = ("holdout" if date >= split else "development"
                                              if pd.Timestamp(trade["exit_date"]) < split else "boundary")
                        observations[(mode, hold)].append(trade)
    results = []
    for (mode, hold), rows in observations.items():
        for cost in COSTS_BPS:
            trial = f"{mode}_h{hold}_bps{int(cost)}"
            execution = replace(settings, maximum_holding_days=hold, slippage_bps=cost)
            candidates = pd.DataFrame(rows)
            if rows:
                slip = cost / 10000
                candidates["net_pnl_per_share"] = (candidates["exit"] * (1 - slip) - candidates["entry"] * (1 + slip)
                                                    - 2 * execution.commission_per_share)
                candidates["net_r_multiple"] = candidates["net_pnl_per_share"] / (candidates["entry"] - candidates["stop"])
            candidates.to_csv(output / f"{trial}_candidates.csv", index=False)
            for partition in ("full", "development", "holdout"):
                sample = candidates.copy() if partition == "full" or not rows else candidates[candidates["partition"] == partition].copy()
                journal, account = build_journal(sample, execution)
                journal, account = enrich_journal(journal, account, sample)
                journal.to_csv(output / f"{trial}_{partition}_journal.csv", index=False)
                (output / f"{trial}_{partition}_journal.md").write_text(render_journal(journal, account, trial + " / " + partition), encoding="utf-8")
                results.append(dict(trial=trial, family=mode, hold=hold, slippage_bps=cost, partition=partition, **account))
    note = ("Hypothesis screening, not validated performance. 60 strategy/hold/cost trials, all reported; "
            "no winner selected. Full and partitions reset equity and must not be summed. "
            "Latest downloaded row excluded conservatively. Per-ticker start dates differ; no pre-listing data. "
            "Current-universe survivorship bias. Shared 2R stop/target harness, not family-specific exits. "
            "Single position, maximum 20% notional by default; cash may be idle. Closed-trade drawdown, not daily MTM. "
            "No earnings filter or opening-gap revalidation. No walk-forward optimization or multiple-testing correction. "
            "Existing holdout has been discussed repeatedly: treat it as a chronological evaluation segment, not untouched validation.")
    manifest = dict(settings=asdict(settings), holds=HOLDS, costs_bps=COSTS_BPS, coverage=coverage,
                    split_date=str(split.date()), trial_count=len(MODES)*len(HOLDS)*len(COSTS_BPS), results=results, note=note)
    (output / "research.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    flat = [{k: v for k, v in row.items() if k not in ("note",)} for row in results]
    pd.DataFrame(flat).to_csv(output / "all_trials.csv", index=False)
    text = "# Long-history strategy lab\n\n" + note + "\n\n"
    text += "| Trial | Partition | Trades | Net P&L | Return | Win rate | Longest loss streak | Closed DD |\n| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |\n"
    for row in results:
        text += (f"| {row['trial']} | {row['partition']} | {row['trades']} | {row['net_pnl']:+,.2f} | "
                 f"{row['return_pct']:+.2f}% | {row['win_rate_pct']:.1f}% | {row['max_consecutive_losses']} | "
                 f"{row['max_closed_trade_drawdown_pct']:.2f}% |\n")
    (output / "research.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
