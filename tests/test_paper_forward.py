import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import pandas as pd
import pytest
import paper_forward as p


class Calendar:
    def sessions_in_range(self,a,b): return pd.bdate_range(a,b)
    def session_open(self,d): return pd.Timestamp(d).tz_localize('UTC')+pd.Timedelta(hours=14,minutes=30)
    def session_close(self,d): return pd.Timestamp(d).tz_localize('UTC')+pd.Timedelta(hours=21)
    def next_session(self,d): return pd.Timestamp(d)+pd.offsets.BDay()


@pytest.fixture
def setup():
    cal=Calendar();now=pd.Timestamp('2026-10-24T12:00:00Z')
    state=p.new_state(['AAA'],'fixture',now)
    frame=pd.DataFrame(dict(Open=100.,High=101.,Low=99.,Close=100.,Volume=1000.),index=pd.bdate_range('2026-09-28','2026-10-23'))
    rows={m:[dict(ticker='AAA',stop=95.,score=1.,quality=.8,votes=['fixture'],families=['fixture'])] for m in p.MODELS}
    with patch.object(p,'signals',return_value=copy.deepcopy(rows)):
        plan=p.make_plan(state,{'AAA':frame},cal,now)
    return cal,now,state,frame,plan


def prices(**extra): return {'AAA':dict(Open=100.,High=101.,Low=99.,Close=100.,Volume=1000.,**extra)}
def close(cal,d): return cal.session_close(pd.Timestamp(d))+pd.Timedelta(hours=1)


def test_prospective_idempotent_and_no_hindsight(setup):
    c,n,s,f,plan=setup
    assert plan['pending']['entry_date']=='2026-10-26' and not s['events']
    assert p.make_plan(plan,{},c,n)==plan
    with pytest.raises(ValueError,match='Too late'): p.make_plan(s,{'AAA':f},c,pd.Timestamp('2026-10-26T16:00:00Z'))
    future=pd.concat([f,f.iloc[-1:].set_axis([pd.Timestamp('2026-10-26')])])
    with pytest.raises(ValueError): p.make_plan(s,{'AAA':future},c,n)
    with pytest.raises(ValueError,match='not complete'): p.settle(plan,'2026-10-26',prices(),c,pd.Timestamp('2026-10-26T18:00:00Z'))


def test_seven_session_exit_risk_and_reconciliation(setup):
    c,_,_,_,s=setup
    for d in pd.bdate_range('2026-10-26',periods=7): s=p.settle(s,p.label(d),prices(),c,close(c,d))
    for b in s['books'].values():
        t=b['trades'][0]
        assert len(b['trades'])==1 and b['position'] is None
        assert t['exit_reason']=='time_exit' and t['held_sessions']==7
        assert isinstance(t['shares'],int) and t['position_cost']<=250 and t['planned_stop_risk']<=15
        assert b['equity']==pytest.approx(1000+sum(t['net_pnl'] for t in b['trades']))
    previous=None
    for e in s['events']:
        assert e['previous_hash']==previous and e['hash']==p.digest({k:v for k,v in e.items() if k!='hash'})
        previous=e['hash']


def test_stop_first_duplicate_guard_and_no_backdated_entries(setup):
    c,_,_,_,s=setup
    bars=prices();bars['AAA'].update(High=111.,Low=94.)
    s=p.settle(s,'2026-10-26',bars,c,close(c,'2026-10-26'));before=p.digest(s)
    with pytest.raises(ValueError): p.settle(s,'2026-10-26',bars,c,close(c,'2026-10-26'))
    assert p.digest(s)==before
    s=p.settle(s,'2026-10-27',prices(),c,close(c,'2026-10-27'))
    assert all(len(b['trades'])==1 and b['trades'][0]['exit_reason']=='stop' and b['position'] is None for b in s['books'].values())


def test_gap_loss_can_exceed_planned_risk(setup):
    c,_,_,_,s=setup;s=p.settle(s,'2026-10-26',prices(),c,close(c,'2026-10-26'))
    bars=prices();bars['AAA'].update(Open=90.,High=91.,Low=89.,Close=90.)
    s=p.settle(s,'2026-10-27',bars,c,close(c,'2026-10-27'));t=s['books'][p.MODELS[0]]['trades'][0]
    assert t['exit_reason']=='gap_stop' and -t['net_pnl']>t['planned_stop_risk']


@pytest.mark.parametrize('change',[{'Close':float('nan')},{'Stock Splits':2.}])
def test_bad_data_preserves_state(setup,change):
    c,_,_,_,s=setup;before=p.digest(s);bars=prices();bars['AAA'].update(change)
    with pytest.raises(ValueError): p.settle(s,'2026-10-26',bars,c,close(c,'2026-10-26'))
    assert p.digest(s)==before


def test_atomic_persistence_and_exclusions(setup):
    _,n,_,_,s=setup
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'state.json';p.save(path,s);obj=json.loads(path.read_text())
        assert obj['sha256']==p.digest(obj['state'])
    for ticker in ('AMD','AMZN'):
        with pytest.raises(ValueError): p.new_state([ticker],'fixture',n)
