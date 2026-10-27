"""Full-equity, three-slot PAPER execution. Historical scores are not forecasts."""
import argparse
import json
import math
import os
import sys
from decimal import Decimal
import pandas as pd

def stats(returns,hits):
    n=len(returns)
    if n<20:
        return dict(rated=False,samples=n,score=0.,hit_fraction=None,lower=0.)
    p=sum(hits)/n;z=1.96
    lower=(p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)
    return dict(rated=True,samples=n,score=sum(returns)/(n+20),hit_fraction=p,lower=lower)

def key(row):
    h=row['history']
    return (not h['rated'],-h['score'],-h['lower'],-row['quality'],row['symbol'])

def size(row,quote,now,equity,cash,gross_room,risk_room,cid):
    bid,ask=float(quote['bp']),float(quote['ap']);ref=float(row['reference'])
    stop=math.floor(float(row['stop'])*100)/100
    age=(now-pd.Timestamp(quote['t']).tz_convert('UTC')).total_seconds()
    if not all(math.isfinite(x) for x in (bid,ask,ref,stop,equity,cash,gross_room,risk_room)) or ref<=0:
        return None
    if not 0<=age<=10 or bid<=0 or ask<max(bid,1) or (ask-bid)/ask>.005 or abs(ask/ref-1)>.02 or not 0<stop<bid:
        return None
    limit=math.ceil(ask*1.0015*100)/100;cost=limit*1.0015;unit=cost-stop*.9985
    allocation=max(0.,equity*.25)
    qty=min(math.floor(max(0.,min(allocation,cash,gross_room))/cost),math.floor(max(0.,min(allocation*.06,risk_room))/unit))
    if qty<1:
        return None
    e,s=Decimal(f'{limit:.2f}'),Decimal(f'{stop:.2f}')
    body=dict(symbol=row['symbol'],qty=str(qty),side='buy',type='limit',time_in_force='gtc',limit_price=f'{limit:.2f}',order_class='bracket',take_profit={'limit_price':f'{e+2*(e-s):.2f}'},stop_loss={'stop_price':f'{stop:.2f}'},extended_hours=False,client_order_id=cid)
    return body,qty*cost,qty*unit

def book(api,engine,equity):
    orders=api.call('GET','/v2/orders',params={'status':'all','limit':500,'nested':'true'})
    opened=api.call('GET','/v2/orders',params={'status':'open','limit':500,'nested':'false'})
    positions=api.call('GET','/v2/positions')
    if len(orders)>=500 or len(opened)>=500:
        raise RuntimeError('Incomplete order-history pagination; manual review required')
    roots=[r for r in orders if r.get('client_order_id','').startswith(engine['PREFIX'])]
    known={x['id'] for r in roots for x in [r]+(r.get('legs') or [])}
    if any(o['id'] not in known for o in opened):
        raise RuntimeError('Unmanaged open order')
    values={};pending=0.;active=set()
    for p in positions:
        if p.get('side')!='long' or float(p['qty'])<=0:
            raise RuntimeError('Unexpected position direction')
        owners=[r for r in roots if r.get('side')=='buy' and r['symbol']==p['symbol'] and math.isclose(float(r.get('filled_qty') or 0)-sum(float(l.get('filled_qty') or 0) for l in r.get('legs') or []),float(p['qty']),rel_tol=1e-9,abs_tol=1e-9)]
        if len(owners)!=1:
            raise RuntimeError('Position ownership mismatch')
        stops=[float(l['stop_price']) for l in owners[0].get('legs') or [] if l.get('stop_price')]
        risk=float(p['qty'])*max(0.,float(p['avg_entry_price'])*1.0015-min(stops)*.9985) if stops else equity*.015
        values[p['symbol']]=[abs(float(p['market_value'])),risk]
    for r in roots:
        if r.get('side')=='buy' and r.get('status') in engine['OPEN']:
            if r['symbol'] in active:
                raise RuntimeError('Duplicate pending entries')
            active.add(r['symbol']);remaining=max(0.,float(r['qty'])-float(r.get('filled_qty') or 0))
            if remaining:
                price=float(r['limit_price'])*1.0015;stops=[float(l['stop_price']) for l in r.get('legs') or [] if l.get('stop_price')]
                risk=remaining*max(0.,price-min(stops)*.9985) if stops else equity*.015
                v=values.setdefault(r['symbol'],[0.,0.]);v[0]+=remaining*price;v[1]+=risk;pending+=remaining*price
    for o in opened:
        values.setdefault(o['symbol'],[0.,0.])
    if len(values)>3 or any(not math.isfinite(x) or x<0 for v in values.values() for x in v):
        raise RuntimeError('Invalid portfolio exposure or more than three occupied slots')
    return values,pending

class View:
    def __init__(self,api,symbol):
        self.api,self.symbol=api,symbol
    def __getattr__(self,name):
        return getattr(self.api,name)
    def call(self,method,path,*args,**kwargs):
        result=self.api.call(method,path,*args,**kwargs)
        return [r for r in result if r['symbol']==self.symbol] if method=='GET' and path in ('/v2/orders','/v2/positions') else result

def rank(api,engine,entries,calendar,now,mode):
    from run_recent_blend import features,candidate,FAMILIES
    closed=[d for d in calendar if engine['session_time'](d,'close')+pd.Timedelta(minutes=20)<=now]
    end=engine['session_time'](closed[-1],'close');history={};symbols=sorted(r['symbol'] for r in entries)
    for offset in range(0,len(symbols),100):
        params=dict(symbols=','.join(symbols[offset:offset+100]),timeframe='1Day',start=(end-pd.Timedelta(days=800)).isoformat(),end=end.isoformat(),adjustment='split',feed=os.getenv('ALPACA_DATA_FEED','iex'),limit=10000);seen=set()
        while True:
            page=api.call('GET','/v2/stocks/bars',params=params,data=True)
            for symbol,bars in page.get('bars',{}).items():
                history.setdefault(symbol,[]).extend(bars)
            token=page.get('next_page_token')
            if not token:
                break
            if token in seen:
                raise RuntimeError('Repeated history token')
            seen.add(token);params['page_token']=token
    weights={g:1/len(FAMILIES) for g in FAMILIES};ranked=[]
    for row in entries:
        assessment=stats([],[]);bars=history.get(row['symbol'],[])
        if bars:
            frame=pd.DataFrame(bars).rename(columns=dict(o='Open',h='High',l='Low',c='Close',v='Volume'))
            frame.index=pd.to_datetime(frame.t,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize();frame=frame.sort_index()
            data=frame[['Open','High','Low','Close','Volume']].astype(float)
            expected=[d['date'] for d in closed if str(frame.index[0].date())<=d['date']<=str(frame.index[-1].date())]
            valid=(list(frame.index.strftime('%Y-%m-%d'))==expected and not frame.index.has_duplicates and str(frame.index[-1].date())==closed[-1]['date'] and all(math.isfinite(float(x)) for x in data.to_numpy().ravel()) and (data[['Open','High','Low','Close']]>0).all().all() and (data.Volume>=0).all() and (data.Low<=data[['Open','Close']].min(axis=1)).all() and (data.High>=data[['Open','Close']].max(axis=1)).all())
            if valid:
                cached=features(data);values=data[['Open','High','Low','Close']].to_numpy();returns=[];hits=[];i=20
                while i+7<len(data):
                    signal=candidate(cached[i],mode,weights,False)
                    if not signal or not 0<float(signal['stop'])<values[i+1][0]:
                        i+=1;continue
                    stop=float(signal['stop']);entry=float(values[i+1][0])*1.0015;target=entry+2*(entry-stop)
                    hit=False;price=float(values[i+7][3]);exit_i=i+7
                    for j in range(i+1,i+8):
                        o,h,l,c=values[j]
                        if o<=stop:
                            price=float(o);exit_i=j;break
                        if o>=target:
                            price=target;hit=True;exit_i=j;break
                        if l<=stop:
                            price=stop;exit_i=j;break
                        if h>=target:
                            price=target;hit=True;exit_i=j;break
                    returns.append((price*.9985-entry)/(entry-stop*.9985));hits.append(hit);i=exit_i+1
                assessment=stats(returns,hits)
        ranked.append(dict(row,history=assessment))
    ranked.sort(key=key)
    for i,row in enumerate(ranked,1):
        row['rank']=i
    report=dict(validated_prediction=False,method='Same-strategy historical seven-session 2R outcomes; nonoverlapping trades; mean shrunk toward zero with 20 prior observations',limitations='In-sample ranking, not calibrated future probabilities; current-universe bias; daily stop-first fills; 15bps per side. Fewer than 20 completed setups remains unrated and eligible after rated candidates.',candidates=ranked)
    (engine['OUT']/'ranked_candidates.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write('# Portfolio ranking\n\nHistorical scores are not validated forecasts.\n\n| Rank | Symbol | Samples | Score R |\n|---:|---|---:|---:|\n')
            for row in ranked[:20]:
                h=row['history'];score=f"{h['score']:.3f}" if h['rated'] else 'UNRATED'
                f.write(f"| {row['rank']} | {row['symbol']} | {h['samples']} | {score} |\n")
    return ranked

def configure(engine):
    def main():
        from alpaca_paper_readiness import readiness
        parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('check','scan','tick'),default='check');args=parser.parse_args()
        out=engine['OUT'];out.mkdir(parents=True,exist_ok=True)
        report=dict(version='portfolio-paper-2r-v3',paper_only=True,mode=args.mode,target_policy='FIXED_2R',historical_target_filter=False,max_positions=3,allocation_fraction=.25,risk_fraction_of_allocation=.06,order_submission_enabled=False,submitted=[])
        try:
            enabled=args.mode=='tick' and os.getenv('ALPACA_PAPER_ENABLED','false').lower()=='true' and os.getenv('ALPACA_PAPER_KILL_SWITCH','false').lower()!='true'
            api=engine['API'](os.getenv('ALPACA_PAPER_KEY_ID',''),os.getenv('ALPACA_PAPER_SECRET_KEY',''),enabled)
            def account():
                a=api.call('GET','/v2/account');check=readiness(a,os.getenv('ALPACA_EXPECTED_PAPER_ACCOUNT_ID',''));report['account_check']=check
                if not check['account_verified']:
                    raise RuntimeError('Account verification failed')
                equity,cash=float(a['equity']),float(a['cash'])
                if not all(math.isfinite(x) for x in (equity,cash)) or equity<=0:
                    raise RuntimeError('Invalid equity or cash')
                return equity,cash
            equity,cash=account();api.verified=True;report.update(order_submission_enabled=enabled,portfolio_equity=equity)
            if args.mode=='check':
                report['status']='READ_ONLY_ACCOUNT_VERIFIED';return
            mode=os.getenv('ALPACA_PAPER_STRATEGY','compression_family')
            if mode not in ('compression_family','balanced_blend'):
                raise RuntimeError('Invalid strategy')
            report['execution_strategy']=mode
            clock=api.call('GET','/v2/clock');now=engine['timestamp'](clock['timestamp']);today=str(now.tz_convert('America/New_York').date())
            calendar=api.call('GET','/v2/calendar',params={'start':str((now-pd.Timedelta(days=900)).date()),'end':today})
            values,pending=book(api,engine,equity)
            for symbol in sorted(values):
                engine['manage'](View(api,symbol),clock,calendar)
            values,pending=book(api,engine,equity);report['occupied_slots']=len(values)
            day=next((d for d in calendar if d['date']==today),None)
            if args.mode=='tick' and (not enabled or not clock['is_open'] or not engine['entry_window'](now,day,engine['session_time']) or len(values)>=3):
                report['status']='BOOK_MANAGED_NO_ENTRY_WINDOW_OR_CAPACITY';return
            rows=engine['universe'](api);planned=engine['candidates'](api,calendar,now,rows)
            ranked=rank(api,engine,planned[mode],calendar,now,mode);report['ranked_candidates']=len(ranked)
            if args.mode=='scan':
                report['status']='READ_ONLY_SP500_AND_SETUP_SCAN';return
            reserved={}
            for row in ranked:
                equity,cash=account();values,pending=book(api,engine,equity);merged={k:list(v) for k,v in values.items()}
                for symbol,v in reserved.items():
                    actual=merged.setdefault(symbol,[0.,0.]);actual[0]=max(actual[0],v[0]);actual[1]=max(actual[1],v[1])
                if len(merged)>=3:
                    break
                if row['symbol'] in merged:
                    continue
                fresh=api.call('GET','/v2/clock');now=engine['timestamp'](fresh['timestamp'])
                if not fresh['is_open'] or not engine['entry_window'](now,day,engine['session_time']):
                    break
                quote=api.call('GET','/v2/stocks/quotes/latest',params={'symbols':row['symbol'],'feed':os.getenv('ALPACA_DATA_FEED','iex')},data=True).get('quotes',{}).get(row['symbol'])
                if not quote:
                    continue
                fresh=api.call('GET','/v2/clock');now=engine['timestamp'](fresh['timestamp'])
                if not fresh['is_open'] or not engine['entry_window'](now,day,engine['session_time']):
                    break
                slot=int((now-engine['session_time'](day,'open')).total_seconds()//1800)
                cid=engine['PREFIX']+'p3-'+today.replace('-','')+'-'+str(slot)+'-'+row['symbol'].replace('.','_')
                if api.client_order(cid):
                    continue
                local_cash=sum(v[0] for s,v in reserved.items() if s not in values)
                sized=size(row,quote,now,equity,max(0.,cash-pending-local_cash),max(0.,.75*equity-sum(v[0] for v in merged.values())),max(0.,.045*equity-sum(v[1] for v in merged.values())),cid)
                if sized is None:
                    continue
                body,cost,risk=sized;reserved[row['symbol']]=[cost,risk];order=api.submit(body)
                report['submitted'].append(dict(symbol=row['symbol'],order_id=order.get('id'),broker_status=order.get('status'),qty=body['qty'],entry_limit=body['limit_price'],stop=body['stop_loss']['stop_price'],target=body['take_profit']['limit_price'],planned_risk=risk,rank=row['rank']))
                if not order.get('id') or order.get('status') in ('rejected','canceled','expired'):
                    raise RuntimeError('Broker did not accept an active entry')
            report['status']='PAPER_BRACKETS_SUBMITTED' if report['submitted'] else 'NO_EXECUTABLE_RANKED_SETUP'
        except Exception as exc:
            report.update(status='FAILED_CLOSED_REVIEW_PAPER_DASHBOARD',error_type=type(exc).__name__)
            raise RuntimeError('Portfolio coordinator stopped; review sanitized report and paper dashboard') from None
        finally:
            text=json.dumps(report,indent=2);(out/'status.json').write_text(text+'\n',encoding='utf-8');print(text)
            if os.getenv('GITHUB_STEP_SUMMARY'):
                with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
                    f.write('\n# Portfolio PAPER coordinator\n\n```json\n'+text+'\n```\n')
    engine['main']=main
    return engine

def selftest():
    now=pd.Timestamp('2026-10-27T14:00:00Z');quote=dict(bp=99.99,ap=100.,t=now.isoformat());row=dict(symbol='TEST',reference=100.,stop=98.,quality=.8)
    body,cost,risk=size(row,quote,now,100000.,100000.,75000.,4500.,'test')
    assert 1000<cost<=25000 and risk<=1500
    assert Decimal(body['take_profit']['limit_price'])-Decimal(body['limit_price'])==2*(Decimal(body['limit_price'])-Decimal(body['stop_loss']['stop_price']))
    assert size(row,quote,now,100000.,0.,75000.,4500.,'cash') is None
    assert size(row,quote,now,100000.,100000.,0.,4500.,'exposure') is None
    assert size(row,quote,now+pd.Timedelta(seconds=11),100000.,100000.,75000.,4500.,'stale') is None
    assert not stats([1.]*19,[True]*19)['rated'] and stats([1.]*20,[True]*20)['rated']
    assert key(dict(row,history=stats([1.]*20,[True]*20)))<key(dict(row,history=stats([],[])))
    class Fake:
        def __init__(self,positions,orders,opened):
            self.positions,self.orders,self.opened=positions,orders,opened
        def call(self,method,path,**kwargs):
            if path=='/v2/positions':
                return self.positions
            return self.opened if kwargs['params']['status']=='open' else self.orders
    roots=[];positions=[];opened=[]
    for i in range(3):
        symbol=f'TEST{i}';roots.append(dict(id=f'root{i}',symbol=symbol,client_order_id=f'fp7v1-test{i}',side='buy',status='filled',qty='10',filled_qty='10',legs=[dict(id=f'stop{i}',stop_price='98',filled_qty='0')]))
        opened.append(dict(id=f'stop{i}',symbol=symbol));positions.append(dict(symbol=symbol,side='long',qty='10',avg_entry_price='100',market_value='1000'))
    engine={'PREFIX':'fp7v1-','OPEN':{'new','partially_filled'}};fake=Fake(positions,roots,opened)
    assert len(book(fake,engine,100000.)[0])==3 and len(View(fake,'TEST0').call('GET','/v2/positions'))==1
    fourth=dict(id='pending4',symbol='TEST3',client_order_id='fp7v1-pending4',side='buy',status='new',qty='10',filled_qty='0',limit_price='100',legs=[dict(id='held4',stop_price='98')])
    for orders,opens in [(roots+[fourth],opened+[dict(id='pending4',symbol='TEST3')]),(roots,opened+[dict(id='unknown',symbol='UNKNOWN')])]:
        try:
            book(Fake(positions,orders,opens),engine,100000.)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Fourth slot or unmanaged order accepted')
    print('Portfolio sizing, 2R, ranking, three-slot reconciliation and reservation checks passed')

if __name__=='__main__':
    if '--selftest' in sys.argv:
        selftest()
    else:
        import run_alpaca_paper_hybrid as entrypoint
        original_install=entrypoint.install
        entrypoint.install=lambda:configure(original_install())
        import paper_scan_repair
        paper_scan_repair.run()
