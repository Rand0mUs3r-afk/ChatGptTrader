# October 2026 entry-only backtest

Only entries dated October 1-31, 2026 are eligible; evaluation ends at the latest completed October session available at run time. Earlier bars are training/warm-up only. Each market/strategy/holding period is an independent flat-start account; one position at a time, no same-day reentry after exit, no FX pooling. Signals/stops use previous close; entry is next session open. Target and net RR are recalculated at that open using only earlier bars and matured historical examples. Current structural SL, historical TP and walk-forward filters apply. 25% allocation and 1.5% equity planned-risk caps; 15 bps/side; zero commissions/dividend cash. Stop-first on ambiguous daily bars; gap-stop losses can exceed plan. Positions still open at cutoff are NOT forced wins/losses: closed P&L and estimated-liquidation unrealized P&L are separate. No future October data is fabricated. This is a development-sample research backtest, with current-universe/survivorship bias, retrospective Yahoo data, and no independent live validation; not a guaranteed forecast.

| Market | Strategy | Hold | As of | Entries | Closed | Won | Lost | Open | Realized P&L | Unrealized P&L | Marked equity | Return % | Drawdown % |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| us (USD) | compression_family | 5 | 2026-10-22 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 1000.00 | 0.00 | 0.00 |
| us (USD) | compression_family | 7 | 2026-10-22 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 1000.00 | 0.00 | 0.00 |
| us (USD) | balanced_blend | 5 | 2026-10-22 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 1000.00 | 0.00 | 0.00 |
| us (USD) | balanced_blend | 7 | 2026-10-22 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 1000.00 | 0.00 | 0.00 |
| tsx (CAD) | compression_family | 5 | 2026-10-22 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 1000.00 | 0.00 | 0.00 |
| tsx (CAD) | compression_family | 7 | 2026-10-22 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 1000.00 | 0.00 | 0.00 |
| tsx (CAD) | balanced_blend | 5 | 2026-10-22 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 1000.00 | 0.00 | 0.00 |
| tsx (CAD) | balanced_blend | 7 | 2026-10-22 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 1000.00 | 0.00 | 0.00 |
