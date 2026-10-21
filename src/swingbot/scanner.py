
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from swingbot.config import DEFAULT_SETTINGS, Settings
from swingbot.data import fetch_benchmark, fetch_history
from swingbot.indicators import calculate_features
from swingbot.risk import attach_position_size
from swingbot.strategies import generate_signals

logger = logging.getLogger(__name__)


def load_tickers(path: str | Path) -> list[str]:
    """Read one ticker per line, ignoring blanks and comments."""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Ticker file not found: {path}")

    tickers = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ticker = line.split("#", 1)[0].strip().upper()
        if ticker:
            tickers.append(ticker)

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(tickers))


def scan_market(
    tickers: list[str],
    settings: Settings = DEFAULT_SETTINGS,
) -> pd.DataFrame:
    """Scan tickers and return qualified candidates."""
    benchmark = fetch_benchmark(settings)
    benchmark_features = calculate_features(
        benchmark, settings=settings
    )

    benchmark_row = benchmark_features.iloc[-1]
    benchmark_uptrend = (
        pd.notna(benchmark_row["EMA20"])
        and pd.notna(benchmark_row["SMA50"])
        and benchmark_row["Close"] > benchmark_row["EMA20"]
        and benchmark_row["EMA20"] > benchmark_row["SMA50"]
    )

    candidates: list[dict] = []

    for ticker in tickers:
        if ticker == settings.benchmark:
            continue

        try:
            bars = fetch_history(ticker, settings)

            features = calculate_features(
                bars,
                benchmark_close=benchmark["Close"],
                settings=settings,
            )

            signals = generate_signals(
                ticker=ticker,
                features=features,
                settings=settings,
                benchmark_uptrend=benchmark_uptrend,
            )

            for signal in signals:
                candidates.append(
                    attach_position_size(signal, settings)
                )

        except Exception:
            logger.exception("Skipping ticker %s", ticker)

    if not candidates:
        return pd.DataFrame()

    report = pd.DataFrame(candidates)

    report = report.sort_values(
        by=["score", "reward_risk"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return report


def save_report(
    report: pd.DataFrame,
    output_path: str | Path = "reports/signals.csv",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report.to_csv(output_path, index=False)
    return output_path
