
import json
import logging
from pathlib import Path

import pandas as pd

from swingbot.backtest import backtest_ticker, summarize_trades
from swingbot.config import DEFAULT_SETTINGS
from swingbot.data import fetch_benchmark, fetch_history
from swingbot.scanner import load_tickers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT = Path("reports")
OUTPUT.mkdir(exist_ok=True)

TRADE_COLUMNS = [
    "ticker",
    "strategy",
    "signal_date",
    "entry_date",
    "exit_date",
    "entry",
    "exit",
    "stop",
    "target",
    "exit_reason",
    "net_pnl_per_share",
    "net_r_multiple",
]


def main():
    settings = DEFAULT_SETTINGS
    tickers = load_tickers("config/tickers.txt")

    # Download benchmark data and log its date range.
    benchmark = fetch_benchmark(settings)

    logger.info(
        "Benchmark data range: %s to %s (%d bars)",
        benchmark.index[0],
        benchmark.index[-1],
        len(benchmark),
    )

    benchmark_close = benchmark["Close"]
    all_trades = []

    # Scan each ticker independently.
    for ticker in tickers:
        if ticker == settings.benchmark:
            continue

        try:
            bars = fetch_history(ticker, settings)

            logger.info(
                "%s data range: %s to %s (%d bars)",
                ticker,
                bars.index[0],
                bars.index[-1],
                len(bars),
            )

            trades = backtest_ticker(
                ticker=ticker,
                bars=bars,
                benchmark_close=benchmark_close,
                settings=settings,
            )

            if not trades.empty:
                all_trades.append(trades)
                logger.info(
                    "%s: %d simulated trades",
                    ticker,
                    len(trades),
                )
            else:
                logger.info(
                    "%s: no historical trades",
                    ticker,
                )

        except Exception:
            logger.exception(
                "Backtest failed for %s",
                ticker,
            )

    # Combine all results, or create an empty report.
    if all_trades:
        results = pd.concat(
            all_trades,
            ignore_index=True,
        )
    else:
        results = pd.DataFrame(
            columns=TRADE_COLUMNS
        )

    # Save detailed trade history.
    trades_path = OUTPUT / "backtest_trades.csv"
    results.to_csv(trades_path, index=False)

    # Calculate summary statistics.
    summary = summarize_trades(results)

    summary["tickers_scanned"] = len(
        [
            ticker
            for ticker in tickers
            if ticker != settings.benchmark
        ]
    )

    summary["benchmark"] = settings.benchmark
    summary["holding_period_sessions"] = (
        settings.maximum_holding_days
    )

    summary["note"] = (
        "Historical simulation, not actual executed trades. "
        "Daily-bar execution assumptions and portfolio limitations "
        "apply. Results are not evidence of future profitability."
    )

    summary_path = OUTPUT / "backtest_summary.json"
    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    print("\nBACKTEST SUMMARY")
    print(json.dumps(summary, indent=2))
    print(f"\nTrade details: {trades_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
