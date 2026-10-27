import time

REASONS = {
    'Incomplete order-history pagination; manual review required': 'ORDER_HISTORY_TRUNCATED',
    'Unmanaged open order': 'OPEN_ORDER_SNAPSHOT_MISMATCH',
    'Unexpected position direction': 'POSITION_DIRECTION_INVALID',
    'Position ownership mismatch': 'POSITION_OWNERSHIP_MISMATCH',
    'Duplicate pending entries': 'DUPLICATE_PENDING_ENTRIES',
    'Invalid portfolio exposure or more than three occupied slots': 'PORTFOLIO_EXPOSURE_INVALID',
}

class ReconciliationError(RuntimeError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)

def reconciled_book(read_once, api, engine, equity, sleep=time.sleep):
    for attempt in range(3):
        try:
            return read_once(api, engine, equity)
        except RuntimeError as exc:
            reason = REASONS.get(str(exc))
            if reason is None:
                raise
            if reason in {'ORDER_HISTORY_TRUNCATED', 'POSITION_DIRECTION_INVALID', 'DUPLICATE_PENDING_ENTRIES', 'PORTFOLIO_EXPOSURE_INVALID'} or attempt == 2:
                raise ReconciliationError(reason) from None
            sleep(2)
