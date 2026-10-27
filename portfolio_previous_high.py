"""Reversible nine-slot paper policy using confirmed prior swing highs."""
import inspect
import math
from decimal import Decimal, ROUND_FLOOR
import pandas as pd

BASELINE_COMMIT = 'd21efc0bc804da9a51b579cb22ead3a92a42c93c'
_namespace = None

def confirmed_highs(frame):
    highs = [float(value) for value in frame['High']]
    return [highs[i] for i in range(len(highs)-3, 1, -1) if math.isfinite(highs[i]) and highs[i] > 0 and highs[i] > max(highs[i-2:i]) and highs[i] >= max(highs[i+1:i+3])]

def select_target(highs, entry):
    entry = Decimal(str(entry))
    if not entry.is_finite() or entry <= 0:
        return None
    for high in highs:
        value = Decimal(str(high))
        if value.is_finite():
            price = value.quantize(Decimal('0.01'), rounding=ROUND_FLOOR)
            if price > entry:
                return f'{price:.2f}'
    return None

def size(row, quote, now, equity, cash, gross_room, risk_room, cid):
    bid, ask = float(quote['bp']), float(quote['ap'])
    ref, stop = float(row['reference']), math.floor(float(row['stop'])*100)/100
    age = (now-pd.Timestamp(quote['t']).tz_convert('UTC')).total_seconds()
    if not all(math.isfinite(x) for x in (bid, ask, ref, stop, equity, cash, gross_room, risk_room)) or ref <= 0:
        return None
    if not 0 <= age <= 10 or bid <= 0 or ask < max(bid, 1) or (ask-bid)/ask > .005 or abs(ask/ref-1) > .02 or not 0 < stop < bid:
        return None
    limit = math.ceil(ask*1.0015*100)/100
    target = select_target(row.get('confirmed_highs', []), limit)
    if target is None:
        return None
    cost, unit = limit*1.0015, limit*1.0015-stop*.9985
    allocation = max(0., equity*.10)
    qty = min(math.floor(max(0., min(allocation, cash, gross_room))/cost), math.floor(max(0., min(allocation*.06, risk_room))/unit))
    if qty < 1:
        return None
    body = dict(symbol=row['symbol'], qty=str(qty), side='buy', type='limit', time_in_force='gtc', limit_price=f'{limit:.2f}', order_class='bracket', take_profit={'limit_price':target}, stop_loss={'stop_price':f'{stop:.2f}'}, extended_hours=False, client_order_id=cid)
    return body, qty*cost, qty*unit

def _replace(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError('Previous-high policy source mismatch; refusing partial installation')
    return source.replace(old, new)

def _load():
    global _namespace
    if _namespace is not None:
        return _namespace
    import portfolio_paper as base
    from portfolio_reconciliation import REASONS
    REASONS['Invalid portfolio exposure or more than nine occupied slots'] = 'PORTFOLIO_EXPOSURE_INVALID'
    ns = dict(vars(base), size=size, confirmed_highs=confirmed_highs, select_target=select_target)
    source = inspect.getsource(base.book)
    source = _replace(source, 'len(values)>3', 'len(values)>9')
    source = _replace(source, 'more than three occupied slots', 'more than nine occupied slots')
    exec(compile(source, base.__file__, 'exec'), ns)
    ns['raw_book'] = ns['book']
    source = inspect.getsource(base.rank)
    source = _replace(source, "assessment=stats([],[]);bars=history.get(row['symbol'],[])", "highs=[];assessment=stats([],[]);bars=history.get(row['symbol'],[])")
    source = _replace(source, 'cached=features(data);values=', 'highs=confirmed_highs(data);cached=features(data);values=')
    source = _replace(source, "stop=float(signal['stop']);entry=float(values[i+1][0])*1.0015;target=entry+2*(entry-stop)", "stop=float(signal['stop']);entry=float(values[i+1][0])*1.0015\n                    target=select_target(confirmed_highs(data.iloc[:i+1]),entry)\n                    if target is None:\n                        i+=1;continue\n                    target=float(target)")
    source = _replace(source, 'ranked.append(dict(row,history=assessment))', "ranked.append(dict(row,history=assessment,confirmed_highs=highs,reference_tp=select_target(highs,row['reference'])))")
    source = _replace(source, 'Same-strategy historical seven-session 2R outcomes;', 'Same-strategy historical seven-session confirmed-prior-high outcomes;')
    source = _replace(source, "validated_prediction=False,method=", "validated_prediction=False,target_policy='PREVIOUS_CONFIRMED_SWING_HIGH',pivot_left=2,pivot_right=2,method=")
    exec(compile(source, base.__file__, 'exec'), ns)
    source = inspect.getsource(base.configure)
    changes = [("version='portfolio-paper-2r-v3'", "version='portfolio-paper-prior-high-v1'"), ("target_policy='FIXED_2R'", "target_policy='PREVIOUS_CONFIRMED_SWING_HIGH'"), ('max_positions=3', 'max_positions=9'), ('allocation_fraction=.25', 'allocation_fraction=.10'), ('len(values)>=3', 'len(values)>=9'), ('len(merged)>=3', 'len(merged)>=9'), ('.75*equity', '.90*equity'), ('.045*equity', '.054*equity'), ('risk_fraction_of_allocation=.06,order_submission_enabled', 'risk_fraction_of_allocation=.06,max_gross_fraction=.90,max_planned_risk_fraction=.054,order_submission_enabled')]
    for old, new in changes:
        source = _replace(source, old, new)
    exec(compile(source, base.__file__, 'exec'), ns)
    _namespace = ns
    return ns

def book(api, engine, equity):
    return _load()['raw_book'](api, engine, equity)

def configure(engine):
    import run_alpaca_paper as base
    ns = _load()
    ns['book'] = book
    engine['candidates'] = base.candidates
    return ns['configure'](engine)
