import pandas as pd
import pytest

from swingbot.research_window import one_year_dates


def test_older_bars_are_warmup_only():
    index = pd.bdate_range("2023-01-01", "2025-01-01")
    dates = one_year_dates(index, index[-1], 220)
    assert dates[0] >= index[-1] - pd.DateOffset(years=1)
    assert dates[-1] == index[-1]
    assert len(dates) >= 250


def test_common_end_is_respected():
    index = pd.bdate_range("2022-01-01", "2025-01-01")
    end = pd.Timestamp("2024-10-01")
    dates = one_year_dates(index, end, 220)
    assert dates.min() >= end - pd.DateOffset(years=1)
    assert dates.max() <= end


def test_short_download_does_not_silently_shorten_window():
    index = pd.bdate_range("2024-01-01", "2025-01-01")
    with pytest.raises(ValueError):
        one_year_dates(index, index[-1], 220)


def test_unsorted_or_duplicate_dates_rejected():
    index = pd.bdate_range("2023-01-01", "2025-01-01")
    with pytest.raises(ValueError):
        one_year_dates(index[::-1], index[-1], 220)
    with pytest.raises(ValueError):
        one_year_dates(index.append(index[-1:]), index[-1], 220)
