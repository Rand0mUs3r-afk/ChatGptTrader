from types import SimpleNamespace
from unittest.mock import Mock, MagicMock
import pandas as pd
import pytest
import alpaca_paper_bot as bot

NOW=pd.Timestamp('2026-10-26T13:32:00Z')
ROW=dict(symbol='TEST',stop=9,reference=10)
QUOTE=dict(bp=9.99,ap=10,t=NOW.isoformat())

def test_write_requires_enable_and_verification():
    for enabled,verified in [(False,False),(True,False),(False,True)]:
        api=bot.API('fake-key','fake-secret',enabled);api.verified=verified;api.opener=Mock()
        with pytest.raises(ValueError): api.call('POST','/v2/orders',{})
        api.opener.open.assert_not_called()

def test_no_live_host_or_redirect_override():
    api=bot.API('fake-key','fake-secret',True);api.verified=True
    response=Mock();response.read.return_value=b'{"id":"paper-order"}'
    api.opener=MagicMock();api.opener.open.return_value.__enter__.return_value=response
    api.call('POST','/v2/orders',{'symbol':'TEST'})
    request=api.opener.open.call_args.args[0]
    assert request.full_url=='https://paper-api.alpaca.markets/v2/orders'
    with pytest.raises(RuntimeError): bot.NoRedirect().redirect_request(None,None,None,None,None,None)
    with pytest.raises(ValueError): api.call('POST','/v2/account',{})
    with pytest.raises(ValueError): api.call('POST','/v2/orders',{},data=True)

def test_idempotent_submission():
    api=bot.API('fake-key','fake-secret',True);api.verified=True
    api.call=Mock(return_value={'id':'existing'})
    assert api.submit({'client_order_id':'stable'})=={'id':'existing'}
    assert api.call.call_count==1
    assert api.call.call_args.args[0]=='GET'

def test_entry_risk_and_cost_caps():
    body=bot.entry_body(ROW,QUOTE,NOW,1000,'stable')
    n=int(body['qty']);price=float(body['limit_price']);stop=float(body['stop_loss']['stop_price'])
    assert n>0 and n*price*1.0015<=250
    assert n*(price*1.0015-stop*.9985)<=15
    assert body['order_class']=='bracket' and body['extended_hours'] is False
    assert float(body['take_profit']['limit_price'])>price>stop

@pytest.mark.parametrize('quote',[
    dict(QUOTE,t=(NOW-pd.Timedelta(seconds=11)).isoformat()),
    dict(QUOTE,t=(NOW+pd.Timedelta(seconds=1)).isoformat()),
    dict(QUOTE,ap=11),dict(QUOTE,bp=9),dict(QUOTE,bp=11),dict(QUOTE,ap=float('nan'))])
def test_bad_quotes_do_not_enter(quote):
    assert bot.entry_body(ROW,quote,NOW,1000,'stable') is None

def test_no_zero_share_or_invalid_stop_order():
    assert bot.entry_body(ROW,QUOTE,NOW,1,'stable') is None
    assert bot.entry_body(dict(ROW,stop=10),QUOTE,NOW,1000,'stable') is None

def table(rows):
    return '<table><tr><th>Company</th><th>Symbol</th></tr>'+''.join('<tr><td>'+name+'</td><td>'+symbol+'</td></tr>' for name,symbol in rows)+'</table>'

def test_universe_duplicate_exclusions_and_symbol_conventions():
    rows=bot.parse_universe(table([('Alpha Corp','AAA'),('Alpha Corp','AAA'),('Berkshire Hathaway','BRK.B'),('Advanced Micro Devices','AMD'),('Amazon','AMZN')]),minimum=4)
    assert [r['broker_symbol'] for r in rows]==['AAA','BRK.B']
    assert rows[1]['yahoo_symbol']=='BRK-B'
    with pytest.raises(ValueError): bot.parse_universe(table([('One','AAA'),('Two','AAA')]),minimum=1)
    with pytest.raises(ValueError): bot.parse_universe(table([('Alpha','AAA')]))
    with pytest.raises(ValueError): bot.parse_universe('<html>blocked</html>')

def test_name_matching_does_not_guess_tickers():
    assert bot.same_name('Example Corporation','Example Inc. Common Stock')
    assert not bot.same_name('IBM','International Business Machines')
    assert not bot.same_name('Example Energy','Example Financial')
    assert not bot.same_name('','')

def fake_account(orders,positions,opened=None,enabled=False):
    api=SimpleNamespace(enabled=enabled,lookup=Mock(return_value=None),submit=Mock())
    def call(method,path,*args,**kwargs):
        if method!='GET': raise AssertionError('unexpected mutation')
        if path=='/v2/orders': return opened or [] if kwargs.get('params',{}).get('status')=='open' else orders
        if path=='/v2/positions': return positions
        raise AssertionError(path)
    api.call=Mock(side_effect=call);return api

def test_unknown_position_or_order_blocks():
    clock=dict(timestamp=NOW.isoformat(),is_open=True)
    for api in [fake_account([], [{'symbol':'TEST','qty':'1','side':'long'}]),fake_account([],[],[{'id':'foreign'}])]:
        with pytest.raises(ValueError): bot.manage(api,clock,[])
        api.submit.assert_not_called()

def test_held_conditional_stop_is_not_active_protection_and_readonly_never_closes():
    parent=dict(id='parent',client_order_id=bot.PREFIX+'20261026',symbol='TEST',side='buy',order_class='bracket',status='partially_filled',filled_qty='1',filled_at=None,submitted_at='2026-10-26T13:31:00Z',legs=[dict(id='stop',side='sell',type='stop',status='held',qty='2',filled_qty='0')])
    api=fake_account([parent],[dict(symbol='TEST',qty='1',side='long')])
    calendar=[dict(date='2026-10-26',open='09:30',close='16:00')]
    assert bot.manage(api,dict(timestamp=NOW.isoformat(),is_open=True),calendar)
    api.submit.assert_not_called()
    assert all(c.args[0]=='GET' for c in api.call.call_args_list)

def test_no_reentry_after_an_owned_exit_same_session():
    order=dict(id='exit',client_order_id=bot.PREFIX+'exit-example',symbol='TEST',side='sell',status='filled',filled_qty='1',filled_at=NOW.isoformat())
    api=fake_account([order],[])
    assert bot.manage(api,dict(timestamp=NOW.isoformat(),is_open=True),[])

@pytest.mark.parametrize('partial',[True,False])
def test_partial_or_seventh_session_exit_cancels_then_rereads_position(partial):
    now=NOW if partial else pd.Timestamp('2026-10-26T19:50:00Z')
    parent=dict(id='parent',client_order_id=bot.PREFIX+'entry',symbol='TEST',side='buy',order_class='bracket',status='partially_filled' if partial else 'filled',filled_qty='1',filled_at=None if partial else '2026-10-16T13:32:00Z',submitted_at=NOW.isoformat(),legs=[dict(id='stop',side='sell',type='stop',status='held' if partial else 'new',qty='1',filled_qty='0')])
    opened=[parent] if partial else [parent['legs'][0]|{'symbol':'TEST'}]
    position=dict(symbol='TEST',qty='1',side='long')
    events=[];open_calls=0
    def call(method,path,*args,**kwargs):
        nonlocal open_calls
        events.append((method,path))
        if method=='DELETE': return None
        if path=='/v2/orders':
            if kwargs.get('params',{}).get('status')=='all': return [parent]
            open_calls+=1;return opened if open_calls==1 else []
        if path=='/v2/positions': return [position]
        if path=='/v2/positions/TEST': return position
        raise AssertionError(path)
    api=SimpleNamespace(enabled=True,call=call,lookup=Mock(return_value=None),submit=Mock())
    calendar=[dict(date=str(d.date()),open='09:30',close='16:00') for d in pd.bdate_range('2026-10-16','2026-10-26')]
    assert bot.manage(api,dict(timestamp=now.isoformat(),is_open=True),calendar)
    body=api.submit.call_args.args[0]
    assert body['side']=='sell' and body['qty']=='1' and body['type']=='market'
    assert ('DELETE','/v2/orders/'+('parent' if partial else 'stop')) in events
    assert events[-1]==('GET','/v2/positions/TEST')

@pytest.mark.parametrize('change',['ok','missing','duplicate','future'])
def test_scan_rejects_inexact_completed_sessions_before_signal_generation(monkeypatch,tmp_path,change):
    import sys
    import types
    dates=pd.bdate_range('2026-09-18','2026-10-26')
    calendar=[dict(date=str(d.date()),open='09:30',close='16:00') for d in dates]
    expected=[d for d in dates if d.date()<NOW.date()][-20:]
    bars=[dict(t=d.strftime('%Y-%m-%d')+'T04:00:00Z',o=9,h=11,l=8,c=10,v=100) for d in expected]
    if change=='missing': bars=bars[1:]
    if change=='duplicate': bars=bars+[dict(bars[-1])]
    if change=='future': bars=bars+[dict(bars[-1],t='2026-10-26T04:00:00Z')]
    parent=types.ModuleType('signal_source');parent.__path__=[]
    module=types.ModuleType('signal_source.run_recent_blend')
    module.features=Mock(return_value=[{'quality':1}])
    module.candidate=Mock(return_value={'stop':9,'score':1})
    module.FAMILIES={'trend':set(),'recovery':set(),'compression':set()}
    monkeypatch.setitem(sys.modules,'signal_source',parent)
    monkeypatch.setitem(sys.modules,'signal_source.run_recent_blend',module)
    monkeypatch.setattr(bot,'OUT',tmp_path)
    api=SimpleNamespace(call=Mock(return_value={'bars':{'TEST':bars}}))
    result=bot.scan(api,calendar,NOW,[{'broker_symbol':'TEST','verified':True}])
    if change=='ok':
        module.features.assert_called_once()
        assert result['compression_family'][0]['symbol']=='TEST'
    else:
        module.features.assert_not_called()
        assert not result['compression_family']
