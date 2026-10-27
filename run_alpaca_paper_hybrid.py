"""Paper-only hybrid targets; historical estimates are not future probabilities."""
import json
import math
from pathlib import Path
import pandas as pd


def historical_target(bars, stop_fraction):
    if not 0 < stop_fraction < 0.25:
        return None
    frame = pd.DataFrame(bars)
    if frame.empty:
        return None
    frame = frame.sort_values('t').drop_duplicates('t')
    values = frame[['o', 'h', 'l', 'c']].astype(float).to_numpy()
    if not all(math.isfinite(float(x)) and x > 0 for row in values for x in row):
        return None
    samples = []
    for i in range(1, len(values)-6, 7):
        entry = values[i][0]
        stop = entry * (1-stop_fraction)
        peak = entry
        for o, high, low, close in values[i:i+7]:
            if low <= stop:
                break
            peak = max(peak, high)
        samples.append((peak/entry-1)/stop_fraction)
    if len(samples) < 30:
        return None
    historical_r = float(pd.Series(samples).quantile(0.4, interpolation='lower'))
    selected_r = min(2.0, historical_r)
    if selected_r < 1.0:
        return None
    return dict(selected_r=selected_r, historical_r=historical_r,
                samples=len(samples), empirical_hit_fraction=sum(x >= selected_r for x in samples)/len(samples),
                method='NONOVERLAPPING_7_SESSION_STOP_FIRST_WINDOWS_40TH_PERCENTILE',
                limitation='Risk-normalized daily history, not setup-conditioned or intraday validation')


def entry_window(now, day, session_time):
    return bool(day and session_time(day, 'open') <= now < session_time(day, 'close')-pd.Timedelta(minutes=15)
                and 0 <= (now-session_time(day, 'open')).total_seconds() % 1800 < 600)


def install():
    import run_alpaca_paper as base
    source = Path(base.__file__).read_text(encoding='utf-8')
    old = "now>session_time(day,'open')+pd.Timedelta(minutes=5)"
    if source.count(old) != 2:
        raise RuntimeError('Unexpected original entry/cancellation gates')
    source = source.replace(old, "now-timestamp(r.get('submitted_at') or r['created_at'])>pd.Timedelta(minutes=30)", 1)
    source = source.replace(old, 'not entry_window(now,day,session_time)', 1)
    old = "current>session_time(day,'open')+pd.Timedelta(minutes=5)"
    if source.count(old) != 2:
        raise RuntimeError('Unexpected original quote gates')
    source = source.replace(old, 'not entry_window(current,day,session_time)')
    old = "cid=PREFIX+'entry-'+today.replace('-','')"
    if source.count(old) != 1:
        raise RuntimeError('Unexpected original order identity')
    source = source.replace(old, "cid=PREFIX+'entry-'+today.replace('-','')+'-'+str(int((now-session_time(day,'open')).total_seconds()//1800))")
    namespace = dict(__name__='hybrid_paper_engine', __file__=base.__file__, entry_window=entry_window)
    exec(compile(source, base.__file__, 'exec'), namespace)
    original_candidates = namespace['candidates']
    original_entry = namespace['entry_body']

    def candidates(api, calendar, now, rows):
        planned = original_candidates(api, calendar, now, rows)
        closed = [d for d in calendar if namespace['session_time'](d, 'close')+pd.Timedelta(minutes=20) <= now]
        end = namespace['session_time'](closed[-1], 'close')
        symbols = sorted({r['symbol'] for entries in planned.values() for r in entries})
        history = {}
        for offset in range(0, len(symbols), 100):
            params = dict(symbols=','.join(symbols[offset:offset+100]), timeframe='1Day',
                          start=(end-pd.Timedelta(days=800)).isoformat(), end=end.isoformat(),
                          adjustment='split', feed=namespace['os'].getenv('ALPACA_DATA_FEED','iex'), limit=10000)
            seen = set()
            while True:
                page = api.call('GET', '/v2/stocks/bars', params=params, data=True)
                for symbol, bars in page.get('bars', {}).items():
                    history.setdefault(symbol, []).extend(bars)
                token = page.get('next_page_token')
                if not token:
                    break
                if token in seen:
                    raise RuntimeError('Repeated history token')
                seen.add(token)
                params['page_token'] = token
        audit = []
        for mode, entries in planned.items():
            accepted = []
            for row in entries:
                fraction = (row['reference']-row['stop'])/row['reference']
                bars = [b for b in history.get(row['symbol'], []) if namespace['timestamp'](b['t']) <= end]
                result = historical_target(bars, fraction)
                audit.append(dict(mode=mode, symbol=row['symbol'], assessment=result,
                                  status='ACCEPTED' if result else 'SKIP_INSUFFICIENT_OR_LOW_REACHABILITY'))
                if result:
                    accepted.append(dict(row, hybrid=result))
            planned[mode] = accepted
        (namespace['OUT']/'hybrid_targets.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
        return planned

    def entry_body(row, quote, now, budget, cid):
        body = original_entry(row, quote, now, budget, cid)
        if body is None or not row.get('hybrid'):
            return None
        entry = float(body['limit_price'])
        stop = float(body['stop_loss']['stop_price'])
        target = math.floor((entry+row['hybrid']['selected_r']*(entry-stop))*100)/100
        if target <= entry or (target-entry)/(entry-stop) < 0.99:
            return None
        body['take_profit']['limit_price'] = f'{target:.2f}'
        return body

    namespace.update(candidates=candidates, entry_body=entry_body)
    return namespace


if __name__ == '__main__':
    install()['main']()
