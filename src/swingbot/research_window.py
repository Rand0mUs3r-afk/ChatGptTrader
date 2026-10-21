"""Evaluation dates with separate pre-window indicator history."""
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


def six_month_dates(index, common_end, minimum_history):
    """Keep the established warmup validation; restrict signals to six months."""
    dates = one_year_dates(index, common_end, minimum_history)
    cutoff = pd.Timestamp(common_end) - pd.DateOffset(months=6)
    dates = dates[dates >= cutoff]
    if len(dates) < 100:
        raise ValueError("Insufficient six-month evaluation history.")
    return dates


def one_month_dates(index, common_end, minimum_history):
    """Use one month for evaluation; require the unchanged warmup before it.

    A month cannot contain 100 sessions. Earlier bars initialize indicators,
    while the runner separately enforces the existing 20-session entry cutoff.
    """
    index = pd.DatetimeIndex(index)
    if minimum_history < 1 or not index.is_monotonic_increasing or index.has_duplicates:
        raise ValueError("Window requires sorted unique dates and positive warmup.")
    end = pd.Timestamp(common_end)
    cutoff = end - pd.DateOffset(months=1)
    if len(index[index < cutoff]) < minimum_history - 1:
        raise ValueError("Insufficient pre-window warmup for one-month evaluation.")
    dates = index[minimum_history - 1:]
    dates = dates[(dates >= cutoff) & (dates <= end)]
    if dates.empty:
        raise ValueError("No evaluation dates in the requested one-month window.")
    return dates
