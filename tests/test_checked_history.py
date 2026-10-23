import numpy as np
import pandas as pd
import pytest
from checked_history import fetch_daily


def bars():
    return pd.DataFrame({'Open':[10.0]*20,'High':[11.0]*20,'Low':[9.0]*20,'Close':[10.0]*20,'Volume':[100]*20},index=pd.bdate_range('2026-09-01',periods=20))


def test_retries_invalid_response_without_filling():
    good = bars()
    bad = good.copy()
    bad.iloc[-1,bad.columns.get_loc('Close')] = np.nan
    responses = iter([bad,good])
    delays = []
    result = fetch_daily('TEST','2026-09-01','2026-10-01',good.index,
        fetcher=lambda:next(responses),sleeper=delays.append)
    assert result.equals(good)
    assert delays == [2]
    assert pd.isna(bad.Close.iloc[-1])


def test_identifies_ticker_column_and_date_after_three_failures():
    bad = bars()
    bad.iloc[-1,bad.columns.get_loc('Close')] = np.nan
    with pytest.raises(RuntimeError,match='FAIL') as caught:
        fetch_daily('FAIL','2026-09-01','2026-10-01',bad.index,
            fetcher=lambda:bad,sleeper=lambda _:None)
    assert 'Close' in str(caught.value)
    assert '2026-09-28' in str(caught.value)
    assert '3 attempts' in str(caught.value)


def test_empty_response_never_becomes_no_setups():
    with pytest.raises(RuntimeError,match='rows=0'):
        fetch_daily('EMPTY','2026-09-01','2026-10-01',bars().index,
            fetcher=lambda:bars().iloc[:0],sleeper=lambda _:None)
