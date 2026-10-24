import pandas as pd
import exchange_calendars as xcals
import october_15_session as old
import backtest_october_2026 as engine
import year_2026_45_session as new


def test_windows_are_isolated_from_october_engine():
    assert new.simulate.__globals__['START'] == pd.Timestamp('2026-01-01')
    assert new.simulate.__globals__['END'] == pd.Timestamp('2027-01-01')
    assert engine.START == pd.Timestamp('2026-10-01')
    assert new.build_book.__globals__['HOLD'] == 45
    assert old.HOLD == 15


def test_historical_calibration_horizon_is_45_not_15(monkeypatch):
    import run_recent_blend
    monkeypatch.setattr(run_recent_blend,'candidate',lambda *args: {'stop':95.0})
    dates = pd.bdate_range('2025-01-01',periods=100)
    frame = pd.DataFrame({'Open':100.0,'High':103.0,'Low':99.0,'Close':100.0},index=dates)
    book = new.build_book(frame,[{}]*100,'compression_family')
    assert [r['end_index'] for r in book] == [95]
    assert all(r['end_index']-r['signal_index'] == 45 for r in book)


def test_january_entries_and_45_session_exit_without_forced_cutoff_close(monkeypatch):
    import run_recent_blend
    monkeypatch.setattr(run_recent_blend,'candidate',lambda *args: dict(stop=95.0,score=1,votes=['fixture'],groups=['fixture']))
    calendar = xcals.get_calendar('XNYS')
    dates = pd.DatetimeIndex(calendar.sessions_in_range('2025-12-01','2026-03-31')).tz_localize(None).normalize()
    frame = pd.DataFrame({'Open':100.0,'High':103.0,'Low':99.0,'Close':100.0},index=dates)
    frame.attrs['ticker'] = 'FIXTURE'
    def assess(*args):
        return dict(target_status='EXPERIMENTAL_CANDIDATE',assessed_target=1000.0,assessed_net_rr=1.0,historical_examples=40,walkforward_examples=20),{}
    summary,journal,_,_ = new.simulate({'FIXTURE':frame},{'FIXTURE':[{}]*len(frame)},'compression_family',45,assessor=assess,fractional=True)
    assert journal[0]['entry_date'] == '2026-01-02'
    assert journal[0]['exit_reason'] == 'time_exit'
    assert journal[0]['held_sessions'] == 45
    assert all(t['held_sessions']<=45 for t in journal)
    assert summary['open_positions'] == 1
    assert not journal[-1]['closed']
    assert new.deadline(calendar,'2026-01-02') == journal[0]['exit_date']
