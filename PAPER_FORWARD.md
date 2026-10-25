# Forward paper test v1

No brokerage integration, real orders, scheduler, or main-branch changes. Two separate USD 1,000 books: compression_family and balanced_blend. Reuses existing signals/order; whole shares, 25% entry allocation, 1.5% planned equity risk, 15 bps/side, structural SL, raw 2R TP, seven trading sessions maximum. Gaps can exceed planned risk.

Install the existing project plus requirements-scanner.txt, then run:

```sh
python -m pytest -q tests/test_paper_forward.py
python paper_forward.py daily
python paper_forward.py status
```

Run daily after US close plus 20 minutes and before the next open. First invocation plans prospectively; no retrospective entries. Alternatively use plan and settle. Missed sessions manage existing positions but cannot open without a pre-open plan. Fills are post-close daily-OHLC simulations, NOT actual opening executions.

Back up reports/paper_forward/state.json and retain it between invocations. Atomic state, exclusive lock, checksums, hash-chained timestamped events, input snapshots, candidates and skip reasons are retained. status.json, closed_trades.csv and events.jsonl are exports. Source/watchlist changes halt for explicit version review. Stale locks and corporate-action halts require operator review; do not discard open positions or reset losses.

Strict Yahoo auto_adjust=False quotes, recent-bar recovery, stop-first ambiguity, gap stops, capped favorable target gaps, time exits; no reporting-boundary liquidation. Splits halt settlement/recent-signal planning; reconciliation is not automated. No commissions/dividend cash/interest. Historical research used adjusted prices and a different earlier universe, so this is a new prospective execution version, not a promise to reproduce its returns. AMD/AMZN excluded. Data-provider metadata and broker fill realism remain unverified. Synthetic-calendar mechanics tests do not prove profitability; full repository/provider execution is pending. No workflow or remote persistence is activated.
