"""Direct verification including broker-held conditional bracket stops."""
import json
import math
import os
import time

ACTIVE = {'new', 'accepted', 'pending_new', 'partially_filled', 'accepted_for_bidding'}

def audit(event):
    text = json.dumps(event, sort_keys=True)
    print(text)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write('\n    ' + text + '\n')

def held_bracket_stop(parent, stop, quantity):
    linked = any(leg.get('id') == stop.get('id') for leg in parent.get('legs') or [])
    filled = float(parent.get('filled_qty') or 0)
    total = float(parent.get('qty') or 0)
    return (stop.get('status') == 'held' and linked and parent.get('order_class') == 'bracket' and parent.get('status') == 'filled' and math.isfinite(filled) and math.isfinite(total) and total > 0 and math.isclose(filled, total, rel_tol=1e-9, abs_tol=1e-9) and filled >= quantity and stop.get('order_class') == 'bracket')

def verify_protection(api, owner, position, sleep=time.sleep):
    symbol = position['symbol']
    quantity = float(position['qty'])
    if not math.isfinite(quantity) or quantity <= 0:
        raise RuntimeError('Invalid position quantity; no liquidation authorized')
    evidence = []
    for attempt in range(3):
        if attempt:
            sleep(2)
        fresh = api.call('GET', '/v2/positions/' + symbol, missing=True)
        if fresh is None or fresh.get('side') != 'long' or not math.isclose(float(fresh['qty']), quantity, rel_tol=1e-9, abs_tol=1e-9):
            audit(dict(event='PROTECTION_CHECK', symbol=symbol, result='POSITION_CHANGED_REVIEW'))
            raise RuntimeError('Position changed during protection verification; no liquidation authorized')
        parent = api.call('GET', '/v2/orders/' + owner['id'], params={'nested': 'true'})
        if parent.get('id') != owner['id'] or parent.get('symbol') != symbol or parent.get('side') != 'buy':
            raise RuntimeError('Parent identity mismatch; no liquidation authorized')
        legs = {leg['id']: leg for source in (owner, parent) for leg in source.get('legs') or [] if leg.get('id')}
        for leg in legs.values():
            if leg.get('side') != 'sell' or leg.get('type') not in ('stop', 'stop_limit'):
                continue
            stop = api.call('GET', '/v2/orders/' + leg['id'])
            evidence.append(dict(attempt=attempt + 1, stop_id=leg['id'], status=stop.get('status')))
            remaining = float(stop.get('qty') or 0) - float(stop.get('filled_qty') or 0)
            price = float(stop.get('stop_price') or 0)
            conditional = held_bracket_stop(parent, stop, quantity)
            valid = (stop.get('id') == leg['id'] and stop.get('symbol') == symbol and stop.get('side') == 'sell' and stop.get('type') in ('stop', 'stop_limit') and (stop.get('status') in ACTIVE or conditional) and math.isfinite(remaining) and remaining >= quantity and math.isfinite(price) and price > 0)
            if valid:
                audit(dict(event='PROTECTION_CHECK', symbol=symbol, parent_id=owner['id'], result='HELD_BRACKET_STOP_VERIFIED' if conditional else 'DIRECT_STOP_VERIFIED', evidence=evidence))
                return True
    audit(dict(event='PROTECTION_CHECK', symbol=symbol, parent_id=owner['id'], result='STOP_NOT_VERIFIED_AFTER_RETRIES', evidence=evidence))
    return False

def audit_exit(owner, position, protected, time_exit):
    audit(dict(event='EXIT_INTENT', symbol=position['symbol'], parent_id=owner['id'], reason='HOLDING_LIMIT' if time_exit else 'STOP_NOT_VERIFIED_AFTER_RETRIES', protection_verified=protected, time_exit=bool(time_exit)))

def patch_source(source):
    lines = [line for line in source.splitlines() if line.startswith('    protected=any(')]
    if len(lines) != 1 or source.count('    if not protected or time_exit:') != 1:
        raise RuntimeError('Unexpected protection gates; refusing partial safety patch')
    source = source.replace(lines[0], '    from paper_exit_safety import verify_protection, audit_exit\n    protected=verify_protection(api,owner,p)')
    return source.replace('    if not protected or time_exit:', '    if not protected or time_exit:\n        audit_exit(owner,p,protected,time_exit)')
