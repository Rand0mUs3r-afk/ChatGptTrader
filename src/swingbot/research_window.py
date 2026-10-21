"""One-year signal evaluation with separate pre-window indicator history."""
import pandas as pd


def one_year_dates(index, common_end, minimum_history):
    index = pd.DatetimeIndex(index)
    if minimum_history < 1 or not index.is_monotonic_increasing or index.has_duplicates:
        raise ValueError("Window requires sorted unique dates and positive warmup.")
    end = pd.Timestamp(common_end)
    cutoff = end - pd.DateOffset(years=1)
    dates = index[minimum_history - 1:]
    dates = dates[(dates >= cutoff) & (dates <= end)]
    if len(dates) < 100:
        raise ValueError("Insufficient one-year evaluation history after indicator warmup.")
    if not len(index[index < cutoff]) >= minimum_history - 1:
        raise ValueError("Insufficient pre-window warmup; refusing a silently shortened one-year test.")
    return dates
