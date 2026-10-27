"""Compatibility entrypoint: fixed-2R PAPER trading; no historical TP filter."""
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path
import pandas as pd

def entry_window(now, day, session_time):
    return bool(day and session_time(day,'open') <= now < session_time(day,'close'))

def normalized_name(value):
    ignored={'inc','incorporated','corp','corporation','company','co','plc','ltd','limited','common','stock','ordinary','share','shares','class','a','b','de'}
    words=re.findall(r'[a-z0-9]+',value.lower().replace('.',''))
    return tuple(sorted(w for w in words if w not in ignored))

def fixed_target(entry, stop):
    entry,stop=Decimal(str(entry)),Decimal(str(stop))
    if not entry.is_finite() or not stop.is_finite() or not 0 < stop < entry:
        raise ValueError('Invalid entry/stop')
    return f'{entry+2*(entry-stop):.2f}'

def install():
    import run_alpaca_paper as base
    from paper_exit_safety import patch_source
    source=patch_source(Path(base.__file__).read_text(encoding='utf-8'))
    old="now>session_time(day,'open')+pd.Timedelta(minutes=5)"
    if source.count(old)!=2:
        raise RuntimeError('Unexpected entry/cancellation gates')
    source=source.replace(old,"now-timestamp(r.get('submitted_at') or r['created_at'])>pd.Timedelta(minutes=30)",1)
    source=source.replace(old,'not entry_window(now,day,session_time)',1)
    old="current>session_time(day,'open')+pd.Timedelta(minutes=5)"
    if source.count(old)!=2:
        raise RuntimeError('Unexpected quote gates')
    source=source.replace(old,'not entry_window(current,day,session_time)')
    old="cid=PREFIX+'entry-'+today.replace('-','')"
    if source.count(old)!=1:
        raise RuntimeError('Unexpected order identity')
    source=source.replace(old,"cid=PREFIX+'entry-'+today.replace('-','')+'-'+str(int((now-session_time(day,'open')).total_seconds()//1800))")
    old="version='github-paper-pilot-v1'"
    if source.count(old)!=1:
        raise RuntimeError('Unexpected report schema')
    source=source.replace(old,"version='github-paper-2r-v2',target_policy='FIXED_2R',historical_target_filter=False")
    source=source.replace('NO_VALID_AFFORDABLE_FRESH_OPENING_SETUP','NO_VALID_AFFORDABLE_FRESH_SETUP')
    namespace=dict(__name__='fixed_2r_paper_engine',__file__=base.__file__,entry_window=entry_window)
    exec(compile(source,base.__file__,'exec'),namespace)
    original_candidates=namespace['candidates']
    original_entry=namespace['entry_body']
    original_name=namespace['same_name']
    original_main=namespace['main']
    def same_name(left,right):
        a,b=normalized_name(left),normalized_name(right)
        return original_name(left,right) or bool(a and a==b)
    def candidates(api,calendar,now,rows):
        planned=original_candidates(api,calendar,now,rows)
        preview={mode:[dict(row,reference_tp=fixed_target(row['reference'],row['stop'])) for row in entries] for mode,entries in planned.items()}
        report=dict(target_policy='FIXED_2R',historical_target_filter=False,
                    note='Reference-close previews only. Actual TP uses the submitted entry limit and rounded stop. Fresh quote, spread, sizing and account checks remain mandatory.',
                    candidates=preview)
        (namespace['OUT']/'fixed_2r_setups.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        if os.getenv('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
                f.write('# Fixed-2R setup scan\n\nHistorical TP filtering is disabled. These are candidates, not approved or filled orders.\n\n')
                for mode,entries in preview.items():
                    f.write(f'## {mode}: {len(entries)} raw candidates\n\n| Symbol | Reference close | Structural stop | Reference 2R TP |\n|---|---:|---:|---:|\n')
                    for row in entries[:20]:
                        f.write(f"| {row['symbol']} | {row['reference']:.2f} | {row['stop']:.2f} | {row['reference_tp']} |\n")
                    f.write('\nFirst 20 shown; complete list is in fixed_2r_setups.json.\n\n')
        return planned
    def entry_body(row,quote,now,budget,cid):
        body=original_entry(row,quote,now,budget,cid)
        if body:
            body['take_profit']['limit_price']=fixed_target(body['limit_price'],body['stop_loss']['stop_price'])
        return body
    def main():
        original_main()
        status=json.loads((namespace['OUT']/'status.json').read_text(encoding='utf-8'))
        if status.get('status') in {'MISSING_PAPER_SECRETS','ACCOUNT_NOT_VERIFIED'}:
            raise RuntimeError('Paper account prerequisites failed; see status Summary')
    namespace.update(candidates=candidates,entry_body=entry_body,same_name=same_name,main=main)
    return namespace

def selftest():
    engine=install()
    assert fixed_target('100.15','98.00')=='104.45'
    assert normalized_name('Copart Inc')==normalized_name('Copart, Inc. (DE) Common Stock')
    assert normalized_name('JB Hunt Transport Services Inc')==normalized_name('J.B. Hunt Transport Services, Inc. Common Stock')
    assert normalized_name('Henry (Jack) & Associates')==normalized_name('Jack Henry & Associates, Inc. Common Stock')
    assert normalized_name('Linde plc Ordinary Share')==normalized_name('Linde plc Ordinary Shares')
    assert not engine['same_name']('Incyte Genomics Inc','Incyte Corp. Common Stock')
    day=dict(date='2026-10-27',open='09:30',close='16:00')
    stamp=lambda s:pd.Timestamp('2026-10-27 '+s,tz='America/New_York').tz_convert('UTC')
    for time,expected in [('09:29',False),('09:30',True),('10:00',True),('10:15',True),('15:45',True),('15:59',True),('16:00',False)]:
        assert entry_window(stamp(time),day,engine['session_time'])==expected
    early=dict(day,close='13:00')
    assert entry_window(stamp('12:59'),early,engine['session_time'])
    assert not entry_window(stamp('13:00'),early,engine['session_time'])
    assert not entry_window(stamp('10:00'),None,engine['session_time'])
    row=dict(symbol='TEST',stop=98.,reference=100.)
    quote=dict(bp=99.99,ap=100.,t=stamp('10:00').isoformat())
    body=engine['entry_body'](row,quote,stamp('10:00'),1000.,'test-fixed-2r')
    assert body and 'hybrid' not in row
    assert Decimal(body['take_profit']['limit_price'])-Decimal(body['limit_price'])==2*(Decimal(body['limit_price'])-Decimal(body['stop_loss']['stop_price']))
    assert engine['entry_body'](row,quote,stamp('10:01'),1000.,'stale') is None
    print('Fixed 2R, stale-quote, name-formatting and full-session entry checks passed')

if __name__=='__main__':
    selftest() if '--selftest' in sys.argv else install()['main']()
