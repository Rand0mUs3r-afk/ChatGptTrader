# Alpaca paper pilot v1

Executable paper-only pilot, not a validated production release or a live-money bot. Existing forward-paper books, frozen research, watchlists and workflows remain unchanged. No credentials are committed.

## Setup

Use a dedicated Alpaca paper account. Keep `ALPACA_PAPER_ENABLED=false` initially. Add repository secrets `ALPACA_PAPER_KEY_ID` and `ALPACA_PAPER_SECRET_KEY`. Run **Alpaca paper pilot / check**, then set repository variable `ALPACA_EXPECTED_PAPER_ACCOUNT_ID` to the returned UUID. Run `check` again, then `scan` and review the generated symbol/name registry and signals. Setting `ALPACA_PAPER_ENABLED=true` authorizes scheduled paper orders. `ALPACA_PAPER_STRATEGY` selects `compression_family` (default) or `balanced_blend`. One account runs one strategy, not two independently funded brokerage books.

## Universe and signals

Import the current public Slickcharts S&P 500 table at runtime; require 500-550 unique source symbols before exclusions, reject malformed names/conflicting duplicates, exclude AMD/AMZN, and retain SPY/QQQ. Preserve company names and broker/Yahoo symbol conventions. Check exact symbols against active tradable Alpaca US-equity assets and normalized names. Unresolved identities remain visible as quarantined rows and cannot trade. Retained ETF names come from the primary broker asset record. Artifacts: `sp500_registry.csv`, `tickers_sp500.txt`, `candidates.json`, `status.json`. No complete verified constituent snapshot is claimed before a successful runtime scan. TSX remains scan-only; original watchlists are not overwritten.

Signal definitions are pinned to `f2b5542f892cf1c6f3724ed68d343b4699354541`. Both compression and balanced candidates are exported with equal family weights and original ranking. Require finite valid OHLCV for the last 20 exact completed broker sessions. Reject missing/duplicate/future sessions per symbol. Alpaca raw daily bars and IEX (default) or entitled SIP data differ from the Yahoo research feed. Expanded-universe pilot results are a separate cohort, not a reproduction of historical results.

## Controls

Only hardcoded paper-trading/data hosts; no credential-bearing redirects or live fallback. Verify expected UUID, ACTIVE/USD status and blocking flags before writes. `check`/`scan` never write. Public-source requests never carry broker credentials. Upstream/authentication/ownership failures stop the coordinator.

One long whole-share position/order at a time; one entry attempt per session across strategies; no re-entry after an owned exit that session. Budget is min(USD 1,000, cash, equity), not a separately deposited or compounding USD 1,000 subaccount. Position cap 25%; modeled stop-risk cap 1.5% of budget, including a 15-bps/side sizing buffer. This is not an actual broker fee or guaranteed loss limit; gaps can exceed planned risk.

Entries require regular-hours broker clock within five minutes of open, quotes at most ten seconds old, spread at most 0.5%, and deviation from prior close at most 2%. Native GTC brackets use a rounded structural SL and 2R TP from the entry limit, not necessarily 2R from actual fill. Deterministic client-ID lookup prevents blind retries after ambiguous POSTs; acceptance is not a fill. Unknown orders/positions, ownership/quantity mismatches, and 500-record reconciliation limits require review.

Broker-native active brackets protect fully filled entries independently of GitHub. Partial/unprotected positions are canceled/flattened on the next successful enabled regular-hours tick. Pending entries outside the opening window are canceled on later ticks. Attempt seventh-session exits in the final 15 minutes, or later open sessions if overdue. Confirm cancellations and re-read positions before market exits. Terminal exit errors and split/quantity mismatches require manual dashboard review.

## Limitations

Weekday five-minute GitHub coordination spans US daylight/standard regular sessions; broker clock/calendar governs holidays/early closes. Scheduling is best-effort, not continuous monitoring or guaranteed opening/closing fills. Delays can miss entry/cancellation/exit deadlines; partial fills can remain temporarily unprotected. No extended-hours execution requested. Offline unit tests do not verify source accessibility, data entitlement, authentication or real broker integration; validate these in the user's paper environment.

Setting the enable variable false stops new coordinator writes/scheduled runs; it does not cancel native broker orders or liquidate positions. Review remaining orders/positions in the dashboard. Artifacts are operational evidence, not a reconciled performance ledger or proof of profitability. Never describe this pilot as a fully validated autonomous system.
