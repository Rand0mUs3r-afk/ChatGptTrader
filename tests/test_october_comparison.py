import pandas as pd
import pytest
from compare_october_models import evaluator, activity_status
from backtest_october_2026 import simulate


def fixture():
    dates = pd.bdate_range('2026-08-20','2026-10-06')
    frame = pd.DataFrame({'Open':100.0,'High':102.0,'Low':98.0,'Close':100.0,'Volume':1000},index=dates)
    frame.attrs['ticker'] = 'TEST'
    features = [dict(active={'inside_breakout'},stops={'inside_breakout':95.0},groups=('compression',),close=100.0,span=4.0,quality=0.5) for _ in dates]
    return dates,frame,features


def test_fixed_benchmark_does_not_apply_adaptive_gates():
    dates,frame,features = fixture()
    diagnostics = []
    def forbidden(*args):
        raise AssertionError('Fixed baseline must not call adaptive assessor')
    check,_ = evaluator('fixed_2r',dates,diagnostics,forbidden)(frame.iloc[:25],dict(provisional_entry=100,stop=95),features[:25])
    assert check['assessed_target'] == 110
    assert diagnostics[0]['ticker'] == 'TEST'
    assert check['target_status'] == 'EXPERIMENTAL_CANDIDATE'
    assert diagnostics[0]['historical_gate'] == 'NOT_APPLIED_BENCHMARK_ONLY'
    assert diagnostics[0]['entry_date'] == str(dates[25].date())


def test_diagnostics_identify_resistance_cap():
    dates,frame,features = fixture()
    diagnostics = []
    def adaptive(*args):
        return dict(target_status='SKIP_LOW_NET_RR',assessed_target=102.6,assessed_net_rr=0.4,
            historical_median_mfe_r=2.0,nearest_confirmed_high=103.0,historical_examples=30,walkforward_examples=12), {}
    evaluator('data_checked',dates,diagnostics,adaptive)(frame.iloc[:25],dict(provisional_entry=100,stop=95),features[:25])
    assert diagnostics[0]['binding_target_constraint'] == 'confirmed_high_cap'
    assert diagnostics[0]['empirical_target_cap'] == 110
    assert diagnostics[0]['resistance_target_cap'] == pytest.approx(102.6)
    assert diagnostics[0]['stop_distance_atr'] == pytest.approx(1.25)


def test_zero_trades_are_not_labeled_success():
    assert activity_status(dict(entries=0,closed_trades=0)) == 'NO_TRADES_NOT_EVALUABLE'
    assert activity_status(dict(entries=1,closed_trades=0)) == 'OPEN_POSITIONS_ONLY'


def test_benchmark_enters_with_existing_october_engine():
    dates,frame,features = fixture()
    diagnostics = []
    summary,journal,_,_ = simulate({'TEST':frame},{'TEST':features},'compression_family',7,
        assessor=evaluator('fixed_2r',dates,diagnostics),fractional=True)
    assert summary['entries'] >= 1
    assert journal[0]['entry_date'] == '2026-10-01'
    assert diagnostics[0]['signal_date'] == '2026-09-30'
