import pandas as pd
import pytest
import exchange_calendars as xcals
import year_2026_45_session as base
import since_2021_45_session as new


def test_2021_window_is_scoped_and_reports_are_separate():
    assert new.simulate.__globals__['START'] == pd.Timestamp('2021-01-01')
    assert new.load_market.__globals__['START'] == pd.Timestamp('2021-01-01')
    assert new.run_base.__globals__['START'] == pd.Timestamp('2021-01-01')
    assert base.START == pd.Timestamp('2026-01-01')
    assert str(new.output_path('reports/year_2026_45_session')) == 'reports/since_2021_45_session'


def test_yearly_returns_compound_without_resetting_accounts():
    daily = pd.DataFrame(dict(date=['2021-01-04','2021-12-31','2022-01-03','2022-12-30'],marked_equity=[1000.,1100.,1050.,990.]))
    summary = dict(starting_equity=1000.,market='us',currency='USD',variant='fixed_2r_control',strategy='trend_family')
    result = new.calendar_year_rows(daily,[],summary)
    assert result[0]['return_pct'] == pytest.approx(10.0)
    assert result[1]['starting_marked_equity'] == 1100.
    assert round(result[1]['return_pct'],8) == -10.
    assert result[1]['ending_marked_equity'] == 990.


def test_entries_include_non_mondays_in_2021(monkeypatch):
    import run_recent_blend
    monkeypatch.setattr(run_recent_blend,'candidate',lambda *args:dict(stop=95.,score=1,votes=['fixture'],groups=['fixture']))
    calendar = xcals.get_calendar('XNYS')
    dates = pd.DatetimeIndex(calendar.sessions_in_range('2020-12-01','2021-01-15')).tz_localize(None).normalize()
    frame = pd.DataFrame(dict(Open=100.,High=103.,Low=99.,Close=100.),index=dates)
    frame.attrs['ticker'] = 'FIXTURE'
    def assess(*args):
        return dict(target_status='EXPERIMENTAL_CANDIDATE',assessed_target=102.,assessed_net_rr=1.,historical_examples=40,walkforward_examples=20),{}
    _,journal,_,_ = new.simulate({'FIXTURE':frame},{'FIXTURE':[{}]*len(frame)},'compression_family',45,assessor=assess,fractional=True)
    assert journal[0]['entry_date'] == '2021-01-04'
    assert any(pd.Timestamp(t['entry_date']).weekday()!=0 for t in journal)
    assert all(pd.Timestamp(t['entry_date'])>=new.START for t in journal)
    assert base.START == pd.Timestamp('2026-01-01')
