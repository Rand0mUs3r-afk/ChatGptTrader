"""Best-effort Alpaca PAPER coordinator. No live-trading endpoint or override."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import pandas as pd

PAPER='https://paper-api.alpaca.markets'
DATA='https://data.alpaca.markets'
SOURCE='https://www.slickcharts.com/sp500'
PREFIX='fp7v1-'
OPEN={'new','accepted','pending_new','partially_filled','held','pending_cancel','accepted_for_bidding'}
PROTECTED=OPEN-{'held','pending_cancel'}
OUT=Path('reports/alpaca_paper')

class API:
    def __init__(self,key,secret,enabled=False,session=None):
        if not key or not secret: raise ValueError('Missing paper credentials')
        if session is None:
            import requests
            session=requests.Session()
        self.session=session; self.enabled=enabled; self.verified=False
        self.headers={'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':secret}
    def call(self,method,path,body=None,params=None,data=False,missing=False):
        if not path.startswith('/v2/') or '?' in path or '..' in path: raise ValueError('Invalid API path')
        if method!='GET' and (method not in ('POST','DELETE') or data or not self.enabled or not self.verified or not (path=='/v2/orders' or re.fullmatch(r'/v2/orders/[a-zA-Z0-9-]+',path))):
            raise ValueError('Paper write not authorized')
        response=self.session.request(method,(DATA if data else PAPER)+path,headers=self.headers,json=body,params=params,timeout=20,allow_redirects=False)
        if missing and response.status_code==404: return None
        if not 200<=response.status_code<300: raise RuntimeError(f'Paper/data HTTP {response.status_code}; body withheld')
        return None if response.status_code==204 else response.json()
    def client_order(self,cid):
        return self.call('GET','/v2/orders:by_client_order_id',params={'client_order_id':cid,'nested':'true'},missing=True)
    def submit(self,body):
        existing=self.client_order(body['client_order_id'])
        return existing if existing else self.call('POST','/v2/orders',body)

def parse_universe(html,minimum=450):
    from bs4 import BeautifulSoup
    found=None
    for table in BeautifulSoup(html,'html.parser').find_all('table'):
        headers=[c.get_text(' ',strip=True) for c in table.find_all('th')]
        if 'Company' in headers and 'Symbol' in headers: found=(table,headers); break
    if found is None: raise ValueError('S&P table unavailable; no guessed fallback')
    table,headers=found; rows={}
    for tr in table.find_all('tr'):
        cells=tr.find_all('td')
        if not cells: continue
        if len(cells)!=len(headers): raise ValueError('Unexpected table schema')
        symbol=cells[headers.index('Symbol')].get_text(' ',strip=True).upper()
        name=cells[headers.index('Company')].get_text(' ',strip=True)
        if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}',symbol) or not name or name==symbol: raise ValueError('Invalid symbol/name')
        if symbol in rows and rows[symbol]['company_name']!=name: raise ValueError('Conflicting duplicate')
        rows[symbol]=dict(broker_symbol=symbol,yahoo_symbol=symbol.replace('.','-'),company_name=name,source=SOURCE)
    if not minimum<=len(rows)<=550: raise ValueError('Incomplete/unexpected S&P universe')
    return [r for s,r in sorted(rows.items()) if s not in {'AMD','AMZN'}]

def same_name(left,right):
    ignored={'inc','incorporated','corp','corporation','company','co','plc','ltd','limited','common','stock','ordinary','shares','class','a','b'}
    clean=lambda s:' '.join(w for w in re.findall(r'[a-z0-9]+',s.lower()) if w not in ignored)
    a,b=clean(left),clean(right)
    return bool(a and b and (a==b or (min(len(a),len(b))>=10 and (a.startswith(b) or b.startswith(a)))))

def universe(api):
    import requests
    # Never reuse the credential-bearing broker session on a public website.
    response=requests.get(SOURCE,headers={'User-Agent':'Mozilla/5.0'},timeout=25,allow_redirects=False)
    if response.status_code!=200: raise RuntimeError('Public S&P source unavailable')
    rows=parse_universe(response.text)
    assets={a['symbol']:a for a in api.call('GET','/v2/assets',params={'status':'active','asset_class':'us_equity'})}
    for symbol in ('SPY','QQQ'):
        a=assets.get(symbol,{})
        rows.append(dict(broker_symbol=symbol,yahoo_symbol=symbol,company_name=a.get('name',''),source='RETAINED_ETF_BROKER_ASSET'))
    for r in rows:
        a=assets.get(r['broker_symbol'],{})
        r.update(broker_name=a.get('name',''),asset_id=a.get('id'))
        r['verified']=bool(a.get('tradable') is True and a.get('class')=='us_equity' and a.get('status')=='active' and same_name(r['company_name'],r['broker_name']))
        r['validation']=('EXACT_BROKER_ASSET_RETAINED_ETF' if r['source']=='RETAINED_ETF_BROKER_ASSET' else 'EXACT_SYMBOL_NORMALIZED_NAME') if r['verified'] else 'QUARANTINED_REVIEW_REQUIRED'
    pd.DataFrame(rows).to_csv(OUT/'sp500_registry.csv',index=False)
    (OUT/'tickers_sp500.txt').write_text('\n'.join(r['yahoo_symbol'] for r in rows)+'\n',encoding='utf-8')
    return rows

def timestamp(value): return pd.Timestamp(value).tz_convert('UTC')
def session_time(row,key): return pd.Timestamp(row['date']+' '+row[key],tz='America/New_York').tz_convert('UTC')

def candidates(api,calendar,now,rows):
    sys.path.insert(0,str(Path('signal_source').resolve()))
    from run_recent_blend import features,candidate,FAMILIES
    import numpy as np
    closed=[d for d in calendar if session_time(d,'close')+pd.Timedelta(minutes=20)<=now]
    if len(closed)<20: raise ValueError('Insufficient completed sessions')
    dates=[d['date'] for d in closed[-20:]]; symbols=sorted(r['broker_symbol'] for r in rows if r['verified'])
    bars={}; feed=os.getenv('ALPACA_DATA_FEED','iex')
    if feed not in ('iex','sip'): raise ValueError('Unsupported feed')
    for offset in range(0,len(symbols),100):
        params=dict(symbols=','.join(symbols[offset:offset+100]),timeframe='1Day',start=dates[0]+'T00:00:00Z',end=session_time(closed[-1],'close').isoformat(),adjustment='raw',feed=feed,limit=10000)
        seen=set()
        while True:
            page=api.call('GET','/v2/stocks/bars',params=params,data=True)
            for symbol,values in page.get('bars',{}).items(): bars.setdefault(symbol,[]).extend(values)
            token=page.get('next_page_token')
            if not token: break
            if token in seen: raise ValueError('Repeated data pagination token')
            seen.add(token); params['page_token']=token
    weights={g:1/len(FAMILIES) for g in FAMILIES}; result={m:[] for m in ('compression_family','balanced_blend')}; rejected=[]
    for symbol in symbols:
        raw=bars.get(symbol,[])
        if not raw: rejected.append(dict(symbol=symbol,reason='NO_COMPLETED_BARS')); continue
        frame=pd.DataFrame(raw).rename(columns=dict(o='Open',h='High',l='Low',c='Close',v='Volume'))
        frame.index=pd.to_datetime(frame.t,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
        frame=frame.sort_index()
        if list(frame.index.strftime('%Y-%m-%d'))!=dates:
            rejected.append(dict(symbol=symbol,reason='MISSING_DUPLICATE_OR_FUTURE_BARS')); continue
        frame=frame[['Open','High','Low','Close','Volume']].apply(pd.to_numeric,errors='raise')
        if not np.isfinite(frame.to_numpy()).all() or (frame[['Open','High','Low','Close']]<=0).any().any() or (frame.Volume<0).any() or (frame.Low>frame[['Open','Close']].min(axis=1)).any() or (frame.High<frame[['Open','Close']].max(axis=1)).any(): raise ValueError('Invalid daily OHLCV')
        f=features(frame)[-1]
        for mode in result:
            match=candidate(f,mode,weights,False)
            if match: result[mode].append(dict(symbol=symbol,stop=float(match['stop']),reference=float(frame.Close.iloc[-1]),score=float(match['score']),quality=float(f['quality'])))
    for mode in result: result[mode].sort(key=lambda r:(-r['score'],-r['quality'] if mode=='balanced_blend' else 0,r['symbol']))
    (OUT/'candidates.json').write_text(json.dumps(dict(signal_session=dates[-1],feed=feed,candidates=result,rejected=rejected),indent=2),encoding='utf-8')
    return result

def entry_body(row,quote,now,budget,cid):
    bid,ask=float(quote['bp']),float(quote['ap']); age=(now-timestamp(quote['t'])).total_seconds()
    if not all(math.isfinite(v) for v in (bid,ask,budget,row['stop'],row['reference'])) or row['reference']<=0: return None
    if not 0<=age<=10 or bid<=0 or ask<bid or ask<1 or (ask-bid)/ask>.005 or abs(ask/row['reference']-1)>.02: return None
    budget=max(0.,min(1000.,budget)); stop=math.floor(row['stop']*100)/100; limit=math.ceil(ask*1.0015*100)/100
    if not 0<stop<bid: return None
    target=math.floor((limit+2*(limit-stop))*100)/100; unit=limit*1.0015-stop*.9985
    qty=min(math.floor(budget*.25/(limit*1.0015)),math.floor(budget*.015/unit))
    if qty<1: return None
    return dict(symbol=row['symbol'],qty=str(qty),side='buy',type='limit',time_in_force='gtc',limit_price=f'{limit:.2f}',order_class='bracket',take_profit={'limit_price':f'{target:.2f}'},stop_loss={'stop_price':f'{stop:.2f}'},extended_hours=False,client_order_id=cid)

def manage(api,clock,calendar):
    orders=api.call('GET','/v2/orders',params={'status':'all','limit':500,'nested':'true'})
    roots=[o for o in orders if o.get('client_order_id','').startswith(PREFIX)]
    known={x['id'] for r in roots for x in [r]+(r.get('legs') or [])}
    opened=api.call('GET','/v2/orders',params={'status':'open','limit':500,'nested':'false'})
    if any(o['id'] not in known for o in opened): raise ValueError('Unmanaged orders: use a dedicated paper account')
    positions=api.call('GET','/v2/positions')
    if len(positions)>1: raise ValueError('Unexpected multiple positions')
    now=timestamp(clock['timestamp']); today=now.tz_convert('America/New_York').date().isoformat()
    day=next((d for d in calendar if d['date']==today),None)
    if not positions:
        if api.enabled:
            for r in roots:
                submitted=timestamp(r.get('submitted_at') or r['created_at']).tz_convert('America/New_York').date().isoformat()
                if r['status'] in OPEN and (submitted!=today or not clock['is_open'] or not day or now>session_time(day,'open')+pd.Timedelta(minutes=5)):
                    api.call('DELETE','/v2/orders/'+r['id'])
        return bool(opened)
    p=positions[0]; qty=float(p['qty'])
    def owns(r):
        remaining=float(r.get('filled_qty') or 0)-sum(float(l.get('filled_qty') or 0) for l in (r.get('legs') or []))
        return r['symbol']==p['symbol'] and r.get('side')=='buy' and qty>0 and math.isclose(remaining,qty,rel_tol=1e-9,abs_tol=1e-9)
    owners=[r for r in roots if owns(r)]
    if len(owners)!=1 or p.get('side')!='long': raise ValueError('Position/order quantities do not reconcile')
    owner=owners[0]; legs=owner.get('legs') or []
    protected=any(l['side']=='sell' and l.get('type') in ('stop','stop_limit') and l['status'] in PROTECTED and float(l['qty'])-float(l.get('filled_qty') or 0)>=qty for l in legs)
    entry=timestamp(owner.get('filled_at') or owner['submitted_at']).tz_convert('America/New_York').date().isoformat()
    age=sum(entry<=d['date']<=today for d in calendar)
    time_exit=bool(day and (age>7 or (age==7 and now>=session_time(day,'close')-pd.Timedelta(minutes=15))))
    if not api.enabled or not clock['is_open']: return True
    if not protected or time_exit:
        cid=PREFIX+'exit-'+owner['id'].replace('-','')[:25]
        existing=api.client_order(cid)
        if existing:
            if existing['status'] not in OPEN: raise RuntimeError('Exit terminal but position remains; manual review required')
            return True
        groups={x['id']:r['id'] for r in roots for x in [r]+(r.get('legs') or [])}; cancelled=set()
        for o in opened:
            group=groups.get(o['id'])
            if group and group not in cancelled and o['symbol']==p['symbol']:
                api.call('DELETE','/v2/orders/'+o['id']); cancelled.add(group)
        remaining=api.call('GET','/v2/orders',params={'status':'open','limit':500,'nested':'false'})
        if any(o['symbol']==p['symbol'] for o in remaining): raise RuntimeError('Cancellation not yet confirmed')
        position=api.call('GET','/v2/positions/'+p['symbol'],missing=True)
        if position:
            if position.get('side')!='long' or not 0<float(position['qty'])<=qty: raise ValueError('Position changed during cancellation')
            api.submit(dict(symbol=p['symbol'],qty=position['qty'],side='sell',type='market',time_in_force='day',client_order_id=cid))
    return True

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--mode',choices=('check','scan','tick'),default='check'); args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    report=dict(paper_only=True,mode=args.mode,order_submission_enabled=False,version='github-paper-pilot-v1')
    try:
        from alpaca_paper_readiness import readiness
        key,secret=os.getenv('ALPACA_PAPER_KEY_ID',''),os.getenv('ALPACA_PAPER_SECRET_KEY','')
        if not key or not secret: report['status']='MISSING_PAPER_SECRETS'; return
        enabled=args.mode=='tick' and os.getenv('ALPACA_PAPER_ENABLED','false').lower()=='true'
        api=API(key,secret,enabled); account=api.call('GET','/v2/account')
        check=readiness(account,os.getenv('ALPACA_EXPECTED_PAPER_ACCOUNT_ID','')); report['account_check']=check
        if not check['account_verified']: report['status']='ACCOUNT_NOT_VERIFIED'; return
        api.verified=True; report['order_submission_enabled']=enabled
        if args.mode=='check': report['status']='READ_ONLY_ACCOUNT_VERIFIED'; return
        mode=os.getenv('ALPACA_PAPER_STRATEGY','compression_family')
        if mode not in ('compression_family','balanced_blend'): raise ValueError('Invalid strategy')
        report['execution_strategy']=mode
        clock=api.call('GET','/v2/clock'); now=timestamp(clock['timestamp']); today=now.tz_convert('America/New_York').date().isoformat()
        calendar=api.call('GET','/v2/calendar',params={'start':str((now-pd.Timedelta(days=100)).date()),'end':today})
        occupied=manage(api,clock,calendar); report['book_busy']=occupied
        if occupied and args.mode=='tick': report['status']='EXISTING_BOOK_RECONCILED'; return
        day=next((d for d in calendar if d['date']==today),None)
        if args.mode=='tick' and (not enabled or not clock['is_open'] or not day or now>session_time(day,'open')+pd.Timedelta(minutes=5)):
            report['status']='NO_NEW_ENTRY_DISABLED_OR_OUTSIDE_OPENING_WINDOW'; return
        rows=universe(api); report['source_symbols']=len(rows); report['broker_verified_symbols']=sum(r['verified'] for r in rows)
        planned=candidates(api,calendar,now,rows)
        if args.mode=='scan': report['status']='READ_ONLY_SP500_AND_SETUP_SCAN'; return
        # One entry attempt across both modes per session; changing strategy cannot bypass this ID.
        cid=PREFIX+'entry-'+today.replace('-','')
        if api.client_order(cid): report['status']='SESSION_ORDER_ALREADY_EXISTS'; return
        cash=min(1000.,float(account['cash']),float(account['equity']))
        for row in planned[mode]:
            fresh=api.call('GET','/v2/clock'); current=timestamp(fresh['timestamp'])
            if not fresh['is_open'] or current>session_time(day,'open')+pd.Timedelta(minutes=5): break
            quote=api.call('GET','/v2/stocks/quotes/latest',params={'symbols':row['symbol'],'feed':os.getenv('ALPACA_DATA_FEED','iex')},data=True).get('quotes',{}).get(row['symbol'])
            if not quote: continue
            fresh=api.call('GET','/v2/clock'); current=timestamp(fresh['timestamp'])
            if not fresh['is_open'] or current>session_time(day,'open')+pd.Timedelta(minutes=5): break
            body=entry_body(row,quote,current,max(0.,cash),cid)
            if body:
                order=api.submit(body); report.update(status='PAPER_BRACKET_SUBMITTED',client_order_id=cid,order_id=order['id'],symbol=row['symbol']); return
        report['status']='NO_VALID_AFFORDABLE_FRESH_OPENING_SETUP'
    except Exception:
        report['status']='FAILED_CLOSED_REVIEW_PAPER_DASHBOARD'
        raise RuntimeError('Paper pilot stopped; credentials and broker response bodies withheld') from None
    finally:
        text=json.dumps(report,indent=2)
        (OUT/'status.json').write_text(text+'\n',encoding='utf-8'); print(text)
        if os.getenv('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
                f.write('# Alpaca PAPER pilot\n\n```json\n'+text+'\n```\n\nBest-effort coordination, not continuous monitoring or guaranteed opening/closing fills.\n')

if __name__=='__main__': main()
