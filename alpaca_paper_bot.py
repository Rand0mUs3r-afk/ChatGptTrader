"""Paper-only Alpaca pilot; separate from the historical/virtual paper books."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import pandas as pd
from alpaca_paper_readiness import NoRedirect, readiness

PAPER = 'https://paper-api.alpaca.markets'
DATA = 'https://data.alpaca.markets'
SOURCE = 'https://www.slickcharts.com/sp500'
PREFIX = 'fp7v1-'
ACTIVE = {'new','accepted','pending_new','partially_filled','accepted_for_bidding'}
OUT = Path('reports/alpaca_paper')

class API:
    def __init__(self, key, secret, enabled=False):
        if not key or not secret: raise ValueError('Missing paper credentials')
        self.headers = {'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':secret,'Accept':'application/json'}
        self.enabled, self.verified = enabled, False
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, method, path, body=None, params=None, data=False, missing=False):
        if not path.startswith('/v2/') or '..' in path or '?' in path: raise ValueError('Invalid API path')
        if method != 'GET' and (data or not self.enabled or not self.verified or not path.startswith('/v2/orders')):
            raise ValueError('Paper write not authorized')
        url = (DATA if data else PAPER) + path
        if params: url += '?' + urllib.parse.urlencode(params)
        headers = dict(self.headers)
        if body is not None: headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(url, data=json.dumps(body,allow_nan=False).encode() if body is not None else None, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=25) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            if missing and error.code == 404: return None
            raise RuntimeError(f'Paper/data API HTTP {error.code}; response body withheld') from None

    def lookup(self, cid):
        return self.call('GET','/v2/orders:by_client_order_id',params={'client_order_id':cid,'nested':'true'},missing=True)

    def submit(self, body):
        existing = self.lookup(body['client_order_id'])
        return existing if existing is not None else self.call('POST','/v2/orders',body)


def parse_universe(html, minimum=500):
    from bs4 import BeautifulSoup
    found = None
    for table in BeautifulSoup(html,'html.parser').find_all('table'):
        headers = [c.get_text(' ',strip=True) for c in table.find_all('th')]
        if 'Company' in headers and 'Symbol' in headers: found = table, headers; break
    if found is None: raise ValueError('S&P source table missing; no guessed fallback')
    table, headers = found; rows = {}
    for tr in table.find_all('tr'):
        cells = tr.find_all('td')
        if len(cells) < len(headers): continue
        symbol = cells[headers.index('Symbol')].get_text(' ',strip=True).upper()
        name = cells[headers.index('Company')].get_text(' ',strip=True)
        if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}',symbol) or not name or name == symbol: raise ValueError('Invalid symbol/name')
        if symbol in rows and rows[symbol]['company_name'] != name: raise ValueError('Conflicting duplicate')
        rows[symbol] = dict(broker_symbol=symbol,yahoo_symbol=symbol.replace('.','-'),company_name=name,source=SOURCE)
    if not minimum <= len(rows) <= 550: raise ValueError('Incomplete/unexpected S&P universe')
    return [r for s,r in sorted(rows.items()) if s not in {'AMD','AMZN'}]


def same_name(left, right):
    ignored = {'inc','incorporated','corp','corporation','company','co','plc','ltd','limited','common','stock','ordinary','shares','class','a','b'}
    def clean(value): return ' '.join(w for w in re.findall(r'[a-z0-9]+',value.lower()) if w not in ignored)
    a,b = clean(left),clean(right)
    return bool(a and b and (a == b or (min(len(a),len(b)) >= 10 and (a.startswith(b) or b.startswith(a)))))


def universe(api):
    # Public-source requests never carry broker credentials.
    request = urllib.request.Request(SOURCE,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=25) as response:
        rows = parse_universe(response.read().decode('utf-8'))
    assets = {a['symbol']:a for a in api.call('GET','/v2/assets',params={'status':'active','asset_class':'us_equity'})}
    for symbol in ('SPY','QQQ'):
        a = assets.get(symbol,{})
        rows.append(dict(broker_symbol=symbol,yahoo_symbol=symbol,company_name=a.get('name',''),source='RETAINED_EXISTING_ETF_BROKER_ASSET'))
    for r in rows:
        a = assets.get(r['broker_symbol'],{})
        r['broker_name'],r['asset_id'] = a.get('name',''),a.get('id','')
        r['verified'] = bool(a.get('tradable') is True and a.get('class') == 'us_equity' and same_name(r['company_name'],r['broker_name']))
        r['validation'] = 'EXACT_BROKER_SYMBOL_NAME_MATCH' if r['verified'] else 'QUARANTINED_REVIEW_REQUIRED'
    pd.DataFrame(rows).to_csv(OUT/'sp500_registry.csv',index=False)
    (OUT/'tickers_sp500.txt').write_text('\n'.join(r['yahoo_symbol'] for r in rows)+'\n',encoding='utf-8')
    return rows


def timestamp(value): return pd.Timestamp(value).tz_convert('UTC')
def session_time(row,key): return pd.Timestamp(row['date']+' '+row[key],tz='America/New_York').tz_convert('UTC')


def scan(api,calendar,now,rows):
    from signal_source.run_recent_blend import features,candidate,FAMILIES
    closed = [d for d in calendar if session_time(d,'close')+pd.Timedelta(minutes=20) <= now]
    if len(closed) < 20: raise ValueError('Insufficient completed sessions')
    dates = [d['date'] for d in closed[-20:]]
    symbols = sorted(r['broker_symbol'] for r in rows if r['verified'])
    feed = os.getenv('ALPACA_DATA_FEED','iex')
    if feed not in ('iex','sip'): raise ValueError('Invalid market-data feed')
    bars = {}
    for start in range(0,len(symbols),100):
        params = dict(symbols=','.join(symbols[start:start+100]),timeframe='1Day',start=dates[0]+'T00:00:00Z',end=session_time(closed[-1],'close').isoformat(),adjustment='raw',feed=feed,limit=10000)
        seen = set()
        while True:
            page = api.call('GET','/v2/stocks/bars',params=params,data=True)
            for symbol,values in page.get('bars',{}).items(): bars.setdefault(symbol,[]).extend(values)
            token = page.get('next_page_token')
            if not token: break
            if token in seen: raise ValueError('Repeated data pagination token')
            seen.add(token);params['page_token'] = token
    results = {m:[] for m in ('compression_family','balanced_blend')};rejected = []
    weights = {g:1/len(FAMILIES) for g in FAMILIES}
    for symbol in symbols:
        raw = bars.get(symbol,[])
        if not raw: rejected.append(dict(symbol=symbol,reason='NO_DATA'));continue
        frame = pd.DataFrame(raw).rename(columns=dict(o='Open',h='High',l='Low',c='Close',v='Volume'))
        frame.index = pd.to_datetime(frame.t,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
        frame = frame.sort_index()
        if list(frame.index.strftime('%Y-%m-%d')) != dates:
            rejected.append(dict(symbol=symbol,reason='MISSING_DUPLICATE_OR_FUTURE_SESSION'));continue
        frame = frame[['Open','High','Low','Close','Volume']].apply(pd.to_numeric,errors='raise')
        import numpy as np
        if not np.isfinite(frame.to_numpy()).all() or (frame[['Open','High','Low','Close']]<=0).any().any() or (frame.Volume<0).any() or (frame.Low>frame[['Open','Close']].min(axis=1)).any() or (frame.High<frame[['Open','Close']].max(axis=1)).any(): raise ValueError('Invalid OHLCV')
        f = features(frame)[-1]
        for mode in results:
            match = candidate(f,mode,weights,False)
            if match: results[mode].append(dict(symbol=symbol,stop=float(match['stop']),reference=float(frame.Close.iloc[-1]),score=float(match['score']),quality=float(f['quality'])))
    for mode in results: results[mode].sort(key=lambda r:(-r['score'],-r['quality'] if mode=='balanced_blend' else 0,r['symbol']))
    (OUT/'candidates.json').write_text(json.dumps(dict(signal_session=dates[-1],feed=feed,candidates=results,rejected=rejected),indent=2,allow_nan=False),encoding='utf-8')
    return results


def entry_body(row,quote,now,budget,cid):
    bid,ask,stop,ref = (float(x) for x in (quote['bp'],quote['ap'],row['stop'],row['reference']))
    if not all(math.isfinite(v) for v in (bid,ask,stop,ref,budget)) or ref<=0 or budget<=0: return None
    age = (now-timestamp(quote['t'])).total_seconds()
    if not 0<=age<=10 or bid<=0 or ask<bid or ask<1 or (ask-bid)/ask>.005 or abs(ask/ref-1)>.02: return None
    stop = math.floor(stop*100)/100;limit = math.ceil(ask*1.0015*100)/100
    if not 0<stop<bid: return None
    target = math.floor((limit+2*(limit-stop))*100)/100
    qty = min(math.floor(budget*.25/(limit*1.0015)),math.floor(budget*.015/(limit*1.0015-stop*.9985)))
    if qty<1: return None
    return dict(symbol=row['symbol'],qty=str(qty),side='buy',type='limit',time_in_force='gtc',limit_price=f'{limit:.2f}',order_class='bracket',take_profit={'limit_price':f'{target:.2f}'},stop_loss={'stop_price':f'{stop:.2f}'},extended_hours=False,client_order_id=cid)


def manage(api,clock,calendar):
    orders = api.call('GET','/v2/orders',params={'status':'all','limit':500,'nested':'true'})
    if len(orders)>=500: raise ValueError('Order-history reconciliation limit reached; review required')
    roots = [o for o in orders if o.get('client_order_id','').startswith(PREFIX)]
    known = {x['id'] for r in roots for x in [r]+(r.get('legs') or [])}
    opened = api.call('GET','/v2/orders',params={'status':'open','limit':500,'nested':'false'})
    if len(opened)>=500 or any(o['id'] not in known for o in opened): raise ValueError('Unmanaged orders; use a dedicated paper account')
    positions = api.call('GET','/v2/positions')
    if len(positions)>1: raise ValueError('Unexpected multiple positions')
    now = timestamp(clock['timestamp']);today = now.tz_convert('America/New_York').date().isoformat()
    day = next((d for d in calendar if d['date']==today),None)
    if not positions:
        for r in roots:
            if api.enabled and r.get('side')=='buy' and r['status'] in ACTIVE and (not clock['is_open'] or not day or now>session_time(day,'open')+pd.Timedelta(minutes=5)):
                api.call('DELETE','/v2/orders/'+r['id'])
        closed_today = any(x.get('side')=='sell' and float(x.get('filled_qty') or 0)>0 and x.get('filled_at') and timestamp(x['filled_at']).tz_convert('America/New_York').date().isoformat()==today for r in roots for x in [r]+(r.get('legs') or []))
        return bool(opened) or closed_today
    p = positions[0];qty = float(p['qty'])
    def owns(r):
        remainder = float(r.get('filled_qty') or 0)-sum(float(l.get('filled_qty') or 0) for l in r.get('legs') or [])
        return r.get('side')=='buy' and r.get('order_class')=='bracket' and r['symbol']==p['symbol'] and qty>0 and math.isclose(qty,remainder,rel_tol=1e-9,abs_tol=1e-9)
    owners = [r for r in roots if owns(r)]
    if len(owners)!=1 or p.get('side')!='long': raise ValueError('Unowned position or quantity mismatch')
    owner = owners[0];cid = PREFIX+'exit-'+owner['id'].replace('-','')[:25]
    closing = api.lookup(cid)
    if closing:
        if closing['status'] in ACTIVE or closing['status']=='pending_cancel': return True
        raise ValueError('Prior exit is terminal but position remains; review required')
    protected = owner.get('status')=='filled' and any(l.get('side')=='sell' and l.get('type') in ('stop','stop_limit') and l['status'] in ACTIVE and float(l['qty'])-float(l.get('filled_qty') or 0)>=qty for l in owner.get('legs') or [])
    entry = timestamp(owner.get('filled_at') or owner['submitted_at']).tz_convert('America/New_York').date().isoformat()
    if not calendar or entry<calendar[0]['date']: raise ValueError('Position age exceeds calendar coverage')
    age = sum(entry<=d['date']<=today for d in calendar)
    expired = bool(day and (age>7 or (age==7 and now>=session_time(day,'close')-pd.Timedelta(minutes=15))))
    if api.enabled and clock['is_open'] and (not protected or expired):
        for o in opened:
            if o['symbol']==p['symbol']: api.call('DELETE','/v2/orders/'+o['id'])
        remaining = api.call('GET','/v2/orders',params={'status':'open','limit':500,'nested':'false'})
        if any(o['symbol']==p['symbol'] for o in remaining): raise RuntimeError('Cancellation not yet confirmed')
        current = api.call('GET','/v2/positions/'+urllib.parse.quote(p['symbol'],safe=''),missing=True)
        if current:
            if current.get('side')!='long' or not 0<float(current['qty'])<=qty: raise ValueError('Position changed while closing')
            api.submit(dict(symbol=p['symbol'],qty=current['qty'],side='sell',type='market',time_in_force='day',client_order_id=cid))
    return True


def run(mode):
    OUT.mkdir(parents=True,exist_ok=True)
    report = dict(paper_only=True,mode=mode,version='github-paper-pilot-v1',order_submission_enabled=False)
    try:
        api = API(os.getenv('ALPACA_PAPER_KEY_ID',''),os.getenv('ALPACA_PAPER_SECRET_KEY',''),mode=='tick' and os.getenv('ALPACA_PAPER_ENABLED','false').lower()=='true')
        account = api.call('GET','/v2/account');check = readiness(account,os.getenv('ALPACA_EXPECTED_PAPER_ACCOUNT_ID',''))
        report['account_check'] = check
        if not check['account_verified']: report['status']='ACCOUNT_NOT_VERIFIED';return
        api.verified = True;report['order_submission_enabled'] = api.enabled
        if mode=='check': report['status']='READ_ONLY_ACCOUNT_VERIFIED';return
        strategy = os.getenv('ALPACA_PAPER_STRATEGY','compression_family')
        if strategy not in ('compression_family','balanced_blend'): raise ValueError('Invalid strategy')
        report['strategy'] = strategy
        clock = api.call('GET','/v2/clock');now = timestamp(clock['timestamp']);today = now.tz_convert('America/New_York').date().isoformat()
        calendar = api.call('GET','/v2/calendar',params={'start':str((now-pd.Timedelta(days=100)).date()),'end':today})
        occupied = manage(api,clock,calendar)
        if occupied and mode=='tick': report['status']='POSITION_ORDER_OR_SAME_SESSION_EXIT_RECONCILED';return
        day = next((d for d in calendar if d['date']==today),None)
        if mode=='tick' and (not api.enabled or not clock['is_open'] or not day or now>session_time(day,'open')+pd.Timedelta(minutes=5)):
            report['status']='NO_ENTRY_DISABLED_OR_OUTSIDE_OPENING_WINDOW';return
        rows = universe(api);report['registry_symbols']=len(rows);report['verified_symbols']=sum(r['verified'] for r in rows)
        planned = scan(api,calendar,now,rows)
        if mode=='scan': report['status']='READ_ONLY_UNIVERSE_AND_SIGNAL_SCAN';return
        cid = PREFIX+today.replace('-','')
        if api.lookup(cid): report['status']='SESSION_ORDER_ALREADY_EXISTS';return
        cash,equity = float(account['cash']),float(account['equity'])
        if not all(math.isfinite(v) and v>=0 for v in (cash,equity)): raise ValueError('Invalid account balances')
        budget = min(1000.,cash,equity)
        for row in planned[strategy]:
            fresh = api.call('GET','/v2/clock');current = timestamp(fresh['timestamp'])
            if not fresh['is_open'] or current>session_time(day,'open')+pd.Timedelta(minutes=5): break
            quote = api.call('GET','/v2/stocks/quotes/latest',params={'symbols':row['symbol'],'feed':os.getenv('ALPACA_DATA_FEED','iex')},data=True).get('quotes',{}).get(row['symbol'])
            if not quote: continue
            body = entry_body(row,quote,current,budget,cid)
            if body:
                order = api.submit(body);report.update(status='PAPER_BRACKET_SUBMITTED',order_id=order['id'],client_order_id=cid,symbol=row['symbol'],broker_status=order.get('status'));return
        report['status']='NO_VALID_AFFORDABLE_FRESH_OPENING_SETUP'
    except Exception:
        report['status']='FAILED_CLOSED_REVIEW_PAPER_DASHBOARD'
        raise RuntimeError('Paper pilot stopped; broker bodies and credentials withheld') from None
    finally:
        text = json.dumps(report,indent=2,allow_nan=False)
        (OUT/'status.json').write_text(text+'\n',encoding='utf-8');print(text)
        if os.getenv('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f: f.write('# Alpaca PAPER pilot\n\n```json\n'+text+'\n```\n')

if __name__=='__main__':
    parser = argparse.ArgumentParser();parser.add_argument('--mode',choices=('check','scan','tick'),default='check')
    run(parser.parse_args().mode)
