import numpy as np
import pandas as pd
import pytest
from checked_history import replace_recent_bars,fetch_daily


def bars():
    dates = pd.date_range('2026-10-20',periods=4,tz='America/New_York')
    return pd.DataFrame(dict(Open=100.0,High=102.0,Low=99.0,Close=101.0,Volume=1000.0),index=dates)


def test_refetch_replaces_whole_damaged_bar_only():
    raw,fresh = bars(),bars()
    raw.loc[raw.index[-1],'Close'] = np.nan
    fresh.loc[fresh.index[-1],['High','Close','Volume']] = [103.0,102.0,1100.0]
    result = replace_recent_bars(raw,fresh,'2026-10-24')
    pd.testing.assert_frame_equal(result.iloc[:-1],raw.iloc[:-1])
    pd.testing.assert_series_equal(result.iloc[-1],fresh.iloc[-1])
    assert np.isnan(raw.Close.iloc[-1])
    assert result.attrs['recent_bar_refetch'] == ['2026-10-23']


def test_still_missing_or_absent_refetch_cannot_be_used():
    raw = bars()
    raw.loc[raw.index[-1],'Close'] = np.nan
    with pytest.raises(ValueError,match='still invalid'):
        replace_recent_bars(raw,raw,'2026-10-24')
    with pytest.raises(ValueError,match='missing 2026-10-23'):
        replace_recent_bars(raw,bars().iloc[:-1],'2026-10-24')


def test_does_not_repair_old_history_or_ignore_invalid_ohlc():
    raw = bars()
    raw.loc[raw.index[0],'Close'] = np.nan
    with pytest.raises(ValueError,match='outside recent'):
        replace_recent_bars(raw,bars(),'2027-01-01')
    fresh = bars()
    fresh.loc[fresh.index[0],'Close'] = 10000.0
    with pytest.raises(ValueError,match='still invalid'):
        replace_recent_bars(raw,fresh,'2026-10-24')


def test_fetch_runs_existing_validator_after_refresh():
    seen = []
    def validate(raw,cutoff):
        seen.append(True)
        assert np.isfinite(raw[["Open","High","Low","Close","Volume"]].to_numpy()).all()
        frame = raw.copy()
        frame.index = frame.index.tz_localize(None).normalize()
        return frame
    raw = bars()
    raw.loc[raw.index[-1],'Close'] = np.nan
    required = raw.index.tz_localize(None).normalize()
    result = fetch_daily('FIXTURE','2026-10-01',pd.Timestamp('2026-10-24'),required,
        fetcher=lambda:raw,tail_fetcher=lambda start:bars(),validator=validate,sleeper=lambda delay:None)
    assert seen == [True]
    assert result.index.equals(required)
    assert result.Close.iloc[-1] == 101.0
    assert result.attrs['recent_bar_refetch'] == ['2026-10-23']
