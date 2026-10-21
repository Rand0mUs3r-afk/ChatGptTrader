
from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

from swingbot.config import DEFAULT_SETTINGS, Settings

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def normalize_bars(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize OHLCV columns and discard invalid observations."""
    if frame.empty:
        raise ValueError("No market data returned.")

    # yfinance can return MultiIndex columns for some downloads.
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)

    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    frame = frame[REQUIRED_COLUMNS].copy()
    frame = frame[~frame.index.duplicated(keep="last")]
    frame = frame.sort_index()

    for column in REQUIRED_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=REQUIRED_COLUMNS)
    frame = frame[frame["Volume"] >= 0]

    if (frame["Close"] <= 0).any():
        frame = frame[frame["Close"] > 0]

    if frame.empty:
        raise ValueError("No valid OHLCV rows remain after cleaning.")

    return frame


def fetch_history(
    ticker: str,
    settings: Settings = DEFAULT_SETTINGS,
) -> pd.DataFrame:
    """Fetch daily historical bars for a single ticker."""
    try:
        frame = yf.Ticker(ticker).history(
            period=settings.period,
            interval=settings.interval,
            auto_adjust=True,
            actions=False,
            raise_errors=True,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Market data download failed for {ticker}: {exc}"
        ) from exc

    frame = normalize_bars(frame)

    if len(frame) < settings.minimum_history:
        raise ValueError(
            f"{ticker} has only {len(frame)} valid rows; "
            f"{settings.minimum_history} required."
        )

    logger.info("Loaded %s bars for %s", len(frame), ticker)
    return frame


def fetch_benchmark(
    settings: Settings = DEFAULT_SETTINGS,
) -> pd.DataFrame:
    return fetch_history(settings.benchmark, settings)
