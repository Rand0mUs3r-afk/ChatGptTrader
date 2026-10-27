"""Resilient public universe loading and credential-free scan diagnostics."""
import json
import os
import re
import sys
from pathlib import Path

SOURCES = ('https://www.slickcharts.com/sp500', 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')

def parse_rows(html, source, minimum=450):
    from bs4 import BeautifulSoup
    for table in BeautifulSoup(html, 'html.parser').find_all('table'):
        header = table.find('tr')
        if header is None:
            continue
        names = [c.get_text(' ', strip=True) for c in header.find_all(['th','td'])]
        company = 'Company' if 'Company' in names else 'Security'
        if 'Symbol' not in names or company not in names:
            continue
        rows = {}
        for tr in table.find_all('tr')[1:]:
            cells = tr.find_all('td')
            if not cells:
                continue
            if len(cells) != len(names):
                raise ValueError('PUBLIC_TABLE_SCHEMA')
            symbol = cells[names.index('Symbol')].get_text(' ',strip=True).upper()
            name = cells[names.index(company)].get_text(' ',strip=True)
            if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}',symbol) or not name:
                raise ValueError('PUBLIC_TABLE_IDENTITY')
            if symbol in rows and rows[symbol]['company_name'] != name:
                raise ValueError('PUBLIC_TABLE_CONFLICT')
            rows[symbol] = dict(broker_symbol=symbol,yahoo_symbol=symbol.replace('.','-'),company_name=name,source=source)
        if not minimum <= len(rows) <= 550:
            raise ValueError('PUBLIC_TABLE_INCOMPLETE')
        return [r for s,r in sorted(rows.items()) if s not in {'AMD','AMZN'}]
    raise ValueError('PUBLIC_TABLE_MISSING')

def load_rows(diagnostics, get=None, minimum=450):
    if get is None:
        import requests
        get = requests.get
    diagnostics['public_sources'] = []
    for source in SOURCES:
        attempt = dict(source=source)
        diagnostics['public_sources'].append(attempt)
        try:
            response = get(source,headers={'User-Agent':'ChatGptTrader-paper-scanner/1.1'},timeout=25,allow_redirects=False)
            attempt['http_status'] = int(response.status_code)
            if response.status_code != 200:
                continue
            rows = parse_rows(response.text,source,minimum)
            attempt['result'] = 'VALIDATED_TABLE'
            diagnostics['selected_public_source'] = source
            return rows
        except Exception as exc:
            attempt['error_type'] = type(exc).__name__
    raise RuntimeError('ALL_PUBLIC_UNIVERSE_SOURCES_FAILED')

def run():
    from run_alpaca_paper_hybrid import install
    engine = install()
    diagnostics = dict(stage='ACCOUNT_AND_BOOK_CHECKS')
    api_class = engine['API']
    original_call = api_class.call
    def call(self, method, path, *args, **kwargs):
        diagnostics['last_api_operation'] = method
        diagnostics['last_api_category'] = 'MARKET_DATA' if kwargs.get('data') else 'PAPER_BROKER'
        try:
            return original_call(self,method,path,*args,**kwargs)
        except Exception as exc:
            diagnostics['error_type'] = type(exc).__name__
            match = re.fullmatch(r'Paper/data HTTP ([0-9]{3}); body withheld',str(exc))
            if match:
                diagnostics['http_status'] = int(match.group(1))
            raise
    api_class.call = call
    def universe(api):
        diagnostics['stage'] = 'PUBLIC_SP500_IMPORT'
        rows = load_rows(diagnostics)
        diagnostics['stage'] = 'ALPACA_ASSET_LOOKUP'
        assets = {a['symbol']:a for a in api.call('GET','/v2/assets',params={'status':'active','asset_class':'us_equity'})}
        diagnostics['stage'] = 'SYMBOL_NAME_VALIDATION'
        for symbol in ('SPY','QQQ'):
            rows.append(dict(broker_symbol=symbol,yahoo_symbol=symbol,company_name=assets.get(symbol,{}).get('name',''),source='RETAINED_ETF_BROKER_ASSET'))
        for row in rows:
            asset = assets.get(row['broker_symbol'],{})
            row.update(broker_name=asset.get('name',''),asset_id=asset.get('id'))
            row['verified'] = bool(asset.get('tradable') is True and asset.get('class')=='us_equity' and asset.get('status')=='active' and engine['same_name'](row['company_name'],row['broker_name']))
            row['validation'] = 'EXACT_SYMBOL_NORMALIZED_NAME' if row['verified'] else 'QUARANTINED_REVIEW_REQUIRED'
        engine['pd'].DataFrame(rows).to_csv(engine['OUT']/'sp500_registry.csv',index=False)
        (engine['OUT']/'tickers_sp500.txt').write_text('\n'.join(r['yahoo_symbol'] for r in rows)+'\n',encoding='utf-8')
        diagnostics['source_symbols'] = len(rows)
        diagnostics['broker_verified_symbols'] = sum(r['verified'] for r in rows)
        if not diagnostics['broker_verified_symbols']:
            raise RuntimeError('NO_VERIFIED_BROKER_SYMBOLS')
        return rows
    original_candidates = engine['candidates']
    def candidates(*args, **kwargs):
        diagnostics['stage'] = 'DAILY_SIGNALS_AND_HYBRID_HISTORY'
        try:
            return original_candidates(*args,**kwargs)
        except Exception as exc:
            diagnostics['error_type'] = type(exc).__name__
            if isinstance(exc,ModuleNotFoundError) and re.fullmatch(r'[A-Za-z0-9_.]+',str(exc.name)):
                diagnostics['missing_module'] = exc.name
            raise
    engine.update(universe=universe,candidates=candidates)
    try:
        engine['main']()
        diagnostics['result'] = 'RETURNED_CHECK_STATUS_JSON_FOR_OUTCOME'
    except Exception as exc:
        diagnostics.setdefault('error_type',type(exc).__name__)
        diagnostics['result'] = 'FAILED_REVIEW_STAGE_AND_STATUS'
        raise RuntimeError('Paper scan failed; see sanitized diagnostics in Summary. No credentials or broker bodies printed.') from None
    finally:
        out = engine['OUT']; out.mkdir(parents=True,exist_ok=True)
        text = json.dumps(diagnostics,indent=2)
        (out/'diagnostics.json').write_text(text+'\n',encoding='utf-8')
        print(text)
        if os.getenv('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
                f.write('\n## Sanitized scan diagnostics\n\n```json\n'+text+'\n```\n')

def selftest():
    from types import SimpleNamespace
    html = '<table><tr><th>Symbol</th><th>Security</th></tr><tr><td>IBM</td><td>IBM</td></tr></table>'
    assert parse_rows(html,SOURCES[1],1)[0]['company_name']=='IBM'
    try:
        parse_rows(html,SOURCES[1])
    except ValueError:
        pass
    else:
        raise AssertionError('Partial universe accepted')
    diagnostics = {}
    def get(url,**kwargs):
        assert not any(k.lower().startswith('apca') for k in kwargs['headers'])
        return SimpleNamespace(status_code=403 if url==SOURCES[0] else 200,text=html)
    rows = load_rows(diagnostics,get,1)
    assert rows[0]['source']==SOURCES[1]
    assert diagnostics['public_sources'][0]['http_status']==403
    print('Public-source parsing, incomplete-table rejection, fallback, provenance and credential-isolation checks passed')

if __name__=='__main__':
    selftest() if '--selftest' in sys.argv else run()
