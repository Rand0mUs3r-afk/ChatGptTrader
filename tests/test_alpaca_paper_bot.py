import pandas as pd
import pytest
from run_alpaca_paper import API,PAPER,entry_body,same_name

class Session:
    def __init__(self): self.calls=[]
    def request(self,method,url,**kwargs):
        self.calls.append((method,url,kwargs))
        class Response:
            status_code=200
            def json(self): return {}
        return Response()

def test_paper_write_guards():
    s=Session();a=API('fake','fake',True,s)
    with pytest.raises(ValueError): a.call('POST','/v2/orders',{})
    assert not s.calls
    a.verified=True;a.call('POST','/v2/orders',{})
    assert s.calls[0][1]==PAPER+'/v2/orders'
    assert s.calls[0][2]['allow_redirects'] is False
    with pytest.raises(ValueError): a.call('POST','/v2/orders',{},data=True)
    a.enabled=False
    with pytest.raises(ValueError): a.call('DELETE','/v2/orders/abc')

def test_risk_and_quotes():
    now=pd.Timestamp('2026-10-26T13:31:00Z')
    row=dict(symbol='ABC',stop=95.,reference=100.)
    quote=dict(bp=99.99,ap=100.,t=str(now))
    o=entry_body(row,quote,now,100000.,'test')
    q=int(o['qty']);p=float(o['limit_price']);s=float(o['stop_loss']['stop_price'])
    assert q*p*1.0015<=250 and q*(p*1.0015-s*.9985)<=15
    assert entry_body(row,quote,now,0.,'test') is None
    assert entry_body(row,quote,now+pd.Timedelta(seconds=11),1000.,'test') is None
    assert not same_name('Apple Inc.','Apple Hospitality REIT')
