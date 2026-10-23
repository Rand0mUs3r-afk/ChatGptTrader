import pytest
from october_15_session import calibrate, GRID, HOLD


def records(n=40):
    return [dict(end_index=(i+1)*HOLD,net_r=[0.4,0.2,0.05,-0.1,-0.2,-0.4],
        hit=[True,False,False,False,False,False]) for i in range(n)]


def test_lower_rr_can_pass_only_with_positive_walkforward_support():
    result = calibrate(records(),600,100,95)
    assert result['selected_raw_r'] == 0.5
    assert result['assessed_target'] == pytest.approx(102.5)
    assert 0 < result['assessed_net_rr'] < 1.25
    assert result['walkforward_examples'] == 20
    assert result['walkforward_mean_net_r'] > 0
    assert result['target_status'] == 'EXPERIMENTAL_CANDIDATE'


def test_unmatured_future_outcomes_do_not_change_selection():
    past = records()
    first = calibrate(past,600,100,95)
    future = dict(end_index=9999,net_r=[100.0]*len(GRID),hit=[True]*len(GRID))
    assert calibrate(past+[future],600,100,95) == first


def test_insufficient_or_negative_evidence_is_not_forced_into_a_trade():
    assert calibrate(records(19),600,100,95)['target_status'] == 'INSUFFICIENT_CALIBRATION'
    bad = [dict(end_index=(i+1)*HOLD,net_r=[-0.2]*len(GRID),hit=[False]*len(GRID)) for i in range(40)]
    assert calibrate(bad,600,100,95)['target_status'] == 'SKIP_NO_CALIBRATION_EDGE'


def test_books_use_complete_nonoverlapping_fifteen_session_horizons(monkeypatch):
    import pandas as pd
    import run_recent_blend
    from october_15_session import build_book
    monkeypatch.setattr(run_recent_blend,'candidate',lambda *args: {'stop':98.0})
    frame = pd.DataFrame({'Open':[100.0]*100,'High':[102.0]*100,'Low':[99.0]*100,'Close':[101.0]*100},index=pd.bdate_range('2025-01-01',periods=100))
    book = build_book(frame,[{}]*len(frame),'compression_family')
    assert [r['end_index'] for r in book] == [65,80,95]
    assert all(r['end_index']-r['signal_index'] == 15 for r in book)
    assert all(len(r['net_r']) == len(GRID) for r in book)


def test_unequal_listing_histories_align_without_losing_calibration_data():
    import pandas as pd
    from october_15_session import align_portfolio
    dates = pd.bdate_range('2025-01-01',periods=100)
    first = pd.DataFrame({'Close':range(100)},index=dates)
    second = first.iloc[10:].copy()
    _,aligned,cached = align_portfolio({'A':first,'B':second},{'A':list(range(100)),'B':list(range(90))})
    assert aligned['A'].index.equals(aligned['B'].index)
    assert cached['A'][0] == 10
    assert cached['B'][0] == 0
    assert len(first) == 100 and len(second) == 90
