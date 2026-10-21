import pandas as pd
import pytest

from swingbot.research_window import one_year_dates, six_month_dates


def test_six_month_window_keeps_old_history_out():
    index = pd.bdate_range("2023-01-01", "2025-01-01")
    dates = six_month_dates(index, index[-1], 220)
    assert dates.min() >= index[-1] - pd.DateOffset(months=6)
    assert dates.max() == index[-1]
    assert 100 <= len(dates) <= 135
    assert dates.isin(one_year_dates(index, index[-1], 220)).all()


def test_dates_after_common_end_are_excluded():
    index = pd.bdate_range("2022-01-01", "2025-01-01")
    end = pd.Timestamp("2024-10-01")
    dates = six_month_dates(index, end, 220)
    assert dates.min() >= end - pd.DateOffset(months=6)
    assert dates.max() <= end


def test_short_input_fails_instead_of_shortening_window():
    index = pd.bdate_range("2024-01-01", "2025-01-01")
    with pytest.raises(ValueError):
        six_month_dates(index, index[-1], 220)


def test_sparse_recent_dates_fail_validation():
    index = pd.bdate_range("2022-01-01", "2024-06-01").append(pd.bdate_range("2024-12-01", "2025-01-01"))
    with pytest.raises(ValueError, match="six-month"):
        six_month_dates(index, index[-1], 220)
