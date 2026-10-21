import numpy as np
import pandas as pd
import pytest

from swingbot.short_history import MODES, prepare_window, setups, simulate


def bars(rows=15):
    close = np.arange(100,100+rows,dtype=float)
    return pd.DataFrame(dict(Open=close-0.3, High=close+0.1, Low=close-1, Close=close, Volume=1000000),
                        index=pd.bdate_range("2025-01-01",periods=rows))


def test_only_15_completed_sessions_retained_before_features():
    data = bars(25)
    window = prepare_window(data, data.index[-1], 15)
    assert len(window)==15 and window.index[-1]==data.index[-2]
    expected = window.copy()
    data.iloc[:5, data.columns.get_loc("Close")]=9999
    pd.testing.assert_frame_equal(prepare_window(data,data.index[-1],15),expected)


def test_too_little_history_rejected():
    with pytest.raises(ValueError):
        prepare_window(bars(10),pd.Timestamp("2025-03-01"),15)


def test_invalid_ohlc_rejected():
    data=bars()
    data.iloc[-1,data.columns.get_loc("High")]=1
    with pytest.raises(ValueError):
        prepare_window(data,pd.Timestamp("2025-03-01"),15)


def test_prefix_signals_do_not_use_future_rows():
    data=bars()
    before=setups(data.iloc[:8])
    data.iloc[8:,data.columns.get_loc("Close")]=1
    assert setups(data.iloc[:8])==before
    assert "breakout3" in before and "momentum_union" in before and "two_vote_blend" in before


@pytest.mark.parametrize("hold",[1,2,3])
def test_replay_sizing_equity_and_no_overlap(hold):
    journal,summary=simulate({"TEST":bars()},"momentum3",hold,5.0)
    assert len(journal)>0
    assert summary["final_equity"]==pytest.approx(25000+journal.net_pnl.sum())
    assert (journal.shares*journal.entry*1.0005<=journal.equity_before*0.2+1e-8).all()
    assert (pd.to_datetime(journal.entry_date).iloc[1:].reset_index(drop=True)>
            pd.to_datetime(journal.exit_date).iloc[:-1].reset_index(drop=True)).all()
    assert set(journal.exit_reason)<= {"time_exit","window_end","target","stop","gap_stop","target_gap"}


def test_window_end_sales_are_explicit():
    journal,_=simulate({"TEST":bars()},"momentum3",3,5.0)
    assert journal.iloc[-1].exit_reason=="window_end"
    assert bool(journal.iloc[-1].window_end_exit)


def test_alphabetical_ticker_ties_are_deterministic():
    journal,_=simulate({"ZZZ":bars(),"AAA":bars()},"momentum3",1,5.0)
    assert set(journal.ticker)=={"AAA"}


def test_cost_stress_changes_effective_pnl():
    _,low=simulate({"TEST":bars()},"momentum3",1,5.0)
    _,high=simulate({"TEST":bars()},"momentum3",1,15.0)
    assert high["net_pnl"]<low["net_pnl"]


def test_zero_trades_have_undefined_win_rate():
    data=bars(); data["Open"]=data["Close"]; data["High"]=data["Close"]+1
    journal,summary=simulate({"TEST":data},"momentum3",1,5.0)
    assert journal.empty and summary["win_rate_pct"] is None


def test_different_session_calendars_rejected():
    with pytest.raises(ValueError):
        simulate({"A":bars(),"B":bars().set_axis(pd.bdate_range("2025-02-01",periods=15))},"momentum3",1,5.0)
    assert len(MODES)==7
