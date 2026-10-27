"""Coordinator entrypoint with bounded, read-only snapshot reconciliation."""
import json
import os
import re
import portfolio_previous_high as portfolio
from portfolio_reconciliation import ReconciliationError, reconciled_book

def run():
    import run_alpaca_paper_hybrid as entrypoint
    import paper_scan_repair
    state = {'failure_code': None, 'last_api_category': None, 'last_api_operation': None}
    original_book = portfolio.book
    original_install = entrypoint.install
    def book(api, engine, equity):
        try:
            return reconciled_book(original_book, api, engine, equity)
        except ReconciliationError as exc:
            state['failure_code'] = exc.reason
            state['failure_stage'] = 'BOOK_RECONCILIATION'
            raise
    portfolio.book = book
    def install():
        engine = portfolio.configure(original_install())
        original_api = engine['API']
        class TrackingAPI(original_api):
            def call(self, method, path, *args, **kwargs):
                state['last_api_operation'] = method
                state['last_api_category'] = 'MARKET_DATA' if kwargs.get('data') else 'PAPER_BROKER'
                state['last_endpoint'] = next((name for prefix, name in (('/v2/orders', 'ORDERS'), ('/v2/positions', 'POSITIONS'), ('/v2/account', 'ACCOUNT'), ('/v2/clock', 'CLOCK'), ('/v2/calendar', 'CALENDAR'), ('/v2/stocks', 'STOCK_DATA'), ('/v2/assets', 'ASSETS')) if path.startswith(prefix)), 'OTHER')
                try:
                    return super().call(method, path, *args, **kwargs)
                except Exception as exc:
                    match = re.fullmatch(r'Paper/data HTTP ([0-9]{3}); body withheld', str(exc))
                    if match:
                        state['failure_code'] = 'BROKER_HTTP_' + match.group(1)
                        state['failure_stage'] = state['last_endpoint']
                    raise
        engine['API'] = TrackingAPI
        main = engine['main']
        def tracked_main():
            try:
                return main()
            except Exception:
                state['failure_code'] = state['failure_code'] or 'UNCLASSIFIED_COORDINATOR_ERROR'
                state.setdefault('failure_stage', state.get('last_endpoint', 'UNKNOWN'))
                path = engine['OUT'] / 'status.json'
                report = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
                report.update(failure_code=state['failure_code'], failure_stage=state['failure_stage'])
                path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
                text = json.dumps(state, indent=2)
                print(text)
                if os.getenv('GITHUB_STEP_SUMMARY'):
                    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
                        summary.write('\n## Coordinator failure code\n\n    ' + text.replace('\n', '\n    ') + '\n')
                raise
        engine['main'] = tracked_main
        return engine
    entrypoint.install = install
    try:
        paper_scan_repair.run()
    finally:
        entrypoint.install = original_install
        portfolio.book = original_book

if __name__ == '__main__':
    run()
