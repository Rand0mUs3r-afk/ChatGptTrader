import json
import logging
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from swingbot.backtest import backtest_ticker, summarize_trades
from swingbot.config import DEFAULT_SETTINGS
from swingbot.data import fetch_benchmark, fetch_history
from swingbot.journal import build_journal, format_journal
from swingbot.scanner import load_tickers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
OUTPUT = Path("reports")
TRADE_COLUMNS = ["ticker", "strategy", "signal_date", "entry_date", "exit_date", "entry",
                 "exit", "stop", "target", "exit_reason", "net_pnl_per_share", "net_r_multiple"]


def main():
    settings = DEFAULT_SETTINGS
    tickers = [t for t in load_tickers("config/tickers.txt") if t != settings.benchmark]
    if not tickers:
        raise ValueError("No non-benchmark tickers configured.")
    benchmark = fetch_benchmark(settings)
    all_trades, failures, successful = [], [], 0
    for ticker in tickers:
        try:
            bars = fetch_history(ticker, settings)
            trades = backtest_ticker(ticker, bars, benchmark["Close"], settings)
            successful += 1
            if not trades.empty:
                all_trades.append(trades)
        except Exception:
            failures.append(ticker)
            logger.exception("Backtest failed for %s", ticker)
    if not successful:
        raise RuntimeError("All ticker backtests failed; no valid journal generated.")
    results = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame(columns=TRADE_COLUMNS)
    journal, account = build_journal(results, settings)
    summary = summarize_trades(results)
    summary.update(
        tickers_scanned=len(tickers), tickers_succeeded=successful, failed_tickers=failures,
        run_status="partial" if failures else "complete", benchmark=settings.benchmark,
        holding_period_sessions=settings.maximum_holding_days, settings=asdict(settings),
        benchmark_start=str(benchmark.index[0]), benchmark_end=str(benchmark.index[-1]),
        journal=account,
        note="Top-level trade statistics use independent candidates; journal equity uses only replayed trades.",
    )
    text = format_journal(account)
    if failures:
        text += "\nWARNING: Partial run. Failed tickers: " + ", ".join(failures) + "\n"
    serialized = json.dumps(summary, indent=2, allow_nan=False)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT / "backtest_trades.csv", index=False)
    journal.to_csv(OUTPUT / "trading_journal.csv", index=False)
    (OUTPUT / "backtest_summary.json").write_text(serialized, encoding="utf-8")
    (OUTPUT / "trading_journal.md").write_text(text, encoding="utf-8")
    print("\nReports: backtest_trades.csv | trading_journal.csv | backtest_summary.json | trading_journal.md")
    print("\n" + text)


if __name__ == "__main__":
    main()
