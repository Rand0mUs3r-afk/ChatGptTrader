import numpy as np
import pandas as pd
import pytest
from history_45_session import prepare_window,fetch_daily,sample_feasibility


def bars():
    return pd.DataFrame(dict(Open=100.0,High=102.0,Low=99.0,Close=101.0,Volume=1000.0),index=pd.bdate_range('2016-01-04','2026-10-23'))


def test_ten_year_request_is_not_silently_cut_to_five_years():
    from run_recent_blend import prepare
    raw = bars()
    frame = prepare_window(raw,'2026-10-24','2016-01-01')
    assert frame.index[0] == pd.Timestamp('2016-01-04')
    assert len(frame)>2500
    assert prepare(raw,'2026-10-24').index[0]>pd.Timestamp('2021-01-01')
    assert raw.index.equals(frame.index)


def test_invalid_old_prices_are_rejected_instead_of_truncated():
    raw = bars()
    raw.loc[raw.index[0],'Close'] = np.nan
    with pytest.raises(ValueError,match='nonfinite'):
        prepare_window(raw,'2026-10-24','2016-01-01')


def test_requested_boundaries_and_duplicate_and_geometry_checks():
    raw = bars()
    result = prepare_window(raw,'2026-01-01','2020-01-01')
    assert (result.index>=pd.Timestamp('2020-01-01')).all()
    assert (result.index<pd.Timestamp('2026-01-01')).all()
    with pytest.raises(ValueError,match='Duplicate'):
        prepare_window(pd.concat([raw,raw.iloc[-1:]]),'2026-10-24','2016-01-01')
    raw.loc[raw.index[0],'High'] = 1.0
    with pytest.raises(ValueError,match='Invalid OHLCV'):
        prepare_window(raw,'2026-10-24','2016-01-01')


def test_fetch_uses_long_window_validator_and_required_sessions():
    raw = bars()
    frame = fetch_daily('FIXTURE','2016-01-01',pd.Timestamp('2026-10-24'),raw.index[-20:],fetcher=lambda:raw,sleeper=lambda delay:None)
    assert frame.index.equals(raw.index)


def test_feasibility_excludes_unmatured_outcomes_and_does_not_relax_gates():
    records = [dict(end_index=50+(i+1)*45,net_r=[.4,.2,.1,0,-.1,-.2],hit=[True,False,False,False,False,False]) for i in range(40)]
    short = sample_feasibility(records,1255)
    assert short['matured_calibration_examples'] == 26
    assert short['maximum_walkforward_examples'] == 6
    assert short['sample_feasibility'] == 'INSUFFICIENT_WALKFORWARD'
    feasible = sample_feasibility(records,1401)
    assert feasible['qualifying_walkforward_examples'] == 10
    assert feasible['sample_feasibility'] == 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL'
    assert sample_feasibility(records+[dict(end_index=9999,net_r=[100.0]*6)],1401) == feasible
