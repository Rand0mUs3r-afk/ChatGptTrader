import pandas as pd
import pytest

from swingbot.research_window import one_month_dates, one_year_dates, six_month_dates


def test_one_month_dates_do_not_include_warmup():
    index = pd.bdate_range("2023-01-01", "2025-01-31")
    dates = one_month_dates(index, index[-1], 220)
    assert dates.min() >= index[-1] - pd.DateOffset(months=1)
    assert dates.max() == index[-1]
    assert 1 <= len(dates) <= 24
    assert dates.isin(six_month_dates(index, index[-1], 220)).all()


def test_common_end_is_respected():
    index = pd.bdate_range("2023-01-01", "2025-01-31")
    end = pd.Timestamp("2024-10-01")
    dates = one_month_dates(index, end, 220)
    assert dates.max() <= end
    assert dates.min() >= end - pd.DateOffset(months=1)


def test_month_is_not_subject_to_100_session_evaluation_requirement():
    index = pd.bdate_range("2023-01-01", "2025-01-31")
    assert len(one_month_dates(index, index[-1], 220)) < 100
    assert len(one_year_dates(index, index[-1], 220)) >= 100


def test_warmup_still_required():
    index = pd.bdate_range("2025-01-01", "2025-01-31")
    with pytest.raises(ValueError):
        one_month_dates(index, index[-1], 220)


def test_empty_requested_month_rejected():
    index = pd.bdate_range("2023-01-01", "2024-11-01")
    with pytest.raises(ValueError, match="one-month"):
        one_month_dates(index, pd.Timestamp("2025-01-01"), 220)


def test_preserved_20_session_rule_leaves_very_few_entry_dates():
    index = pd.bdate_range("2023-01-01", "2025-01-31")
    dates = one_month_dates(index, index[-1], 220)
    eligible = dates[dates.isin(index[:-20])]
    assert len(eligible) <= 4
