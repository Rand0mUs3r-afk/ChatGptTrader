# 2026 year-to-date entries - maximum 45 trading sessions (history corrected; AMD and AMZN excluded)

HISTORY-WINDOW FIX: the requested longer history is retained rather than truncated to five years. AMD and AMZN are absent from the pinned US source watchlist by user request. Results differ in history coverage and US universe from earlier runs; this is not an identical-universe or target-distance-only comparison. Evidence thresholds are unchanged, and feasible sample counts do not establish a trading edge.

2026 YEAR-TO-DATE ENTRY RESEARCH; maximum 45 TRADING SESSIONS, entry is session one. Entries from January 1 through latest completed 2026 exchange session, never future prices. SL/TP may exit earlier; open positions are marked separately, not forced wins/losses. Up to ten years of pre-2026 history are requested and retained when available, without the older five-year truncation. Per-ticker/strategy feasibility audits use only outcomes matured before the first eligible entry open and latest entry open. Feasible sample counts do NOT imply positive edge or trade approval. Later pre-entry matured 2026 outcomes may update the model causally. Same empirical target grid, 20 calibration/10 qualifying walk-forward minimums, positive mean net-R checks and 30-example training window as the 15-session experiment. Targets/stops are not mechanically scaled with holding time. Shorter-listed stocks may lack sufficient empirical evidence and are rejected, not granted looser thresholds. At least 60 pre-January bars are required for price-feature warm-up; exclusions are disclosed. This is a retrospective current-baseline-watchlist study, NOT a reconstructed point-in-time 2026 universe. Known later TSX additions retain their recorded eligibility dates, not January 1. Historical hit rates are descriptive, not forecast probabilities; old regimes and selection bias remain. Compression/balanced/trend-family signals, original pattern stops, empirical targets and labeled fixed-2R controls. Separate USD/CAD accounts, one position at a time, 25% allocation and 1.5% planned equity-risk caps, 15 bps/side; gaps can exceed planned risk. No commissions or dividend cash, daily stop-first fills, fractional broker/order eligibility unverified. Zero entries are not evaluable. Independent scenarios must not be summed as one portfolio. No orders or live strategy promotion. Original October experiments and reports remain unchanged.

```text
market          variant           strategy       asof  entries  closed_trades  wins  losses  open_positions  full_horizon_mature_entries  ending_marked_equity  total_return_pct  max_marked_drawdown_pct        activity_status
    us        empirical compression_family 2026-10-23       17             17     7      10               0                           11            990.532872         -0.946713                 8.137132 RESEARCH_NOT_VALIDATED
    us fixed_2r_control compression_family 2026-10-23       15             15     6       9               0                           11           1001.245639          0.124564                 7.622421 RESEARCH_NOT_VALIDATED
    us        empirical     balanced_blend 2026-10-23       20             20     9      11               0                           15           1067.493228          6.749323                 5.449590 RESEARCH_NOT_VALIDATED
    us fixed_2r_control     balanced_blend 2026-10-23       23             22     6      16               1                           21            906.439943         -9.356006                11.423589 RESEARCH_NOT_VALIDATED
    us        empirical       trend_family 2026-10-23       14             13     5       8               1                            9            982.489215         -1.751079                 7.994169 RESEARCH_NOT_VALIDATED
    us fixed_2r_control       trend_family 2026-10-23       24             24     7      17               0                           19            942.811291         -5.718871                12.535114 RESEARCH_NOT_VALIDATED
   tsx        empirical compression_family 2026-10-23       19             18     9       9               1                           17           1071.312387          7.131239                 4.434714 RESEARCH_NOT_VALIDATED
   tsx fixed_2r_control compression_family 2026-10-23       17             16     6      10               1                           14           1038.058380          3.805838                 6.562013 RESEARCH_NOT_VALIDATED
   tsx        empirical     balanced_blend 2026-10-23       16             15     6       9               1                           15           1002.458486          0.245849                 6.099079 RESEARCH_NOT_VALIDATED
   tsx fixed_2r_control     balanced_blend 2026-10-23       23             22     8      14               1                           18            994.921805         -0.507819                 6.236841 RESEARCH_NOT_VALIDATED
   tsx        empirical       trend_family 2026-10-23       20             19     8      11               1                           16           1030.815307          3.081531                 5.328864 RESEARCH_NOT_VALIDATED
   tsx fixed_2r_control       trend_family 2026-10-23       17             16     7       9               1                           15           1012.197963          1.219796                 7.299205 RESEARCH_NOT_VALIDATED
```

## Pre-entry sample feasibility (not trade approval)

- us/compression_family/first_eligible_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 12, 'INSUFFICIENT_WALKFORWARD': 2}
- us/compression_family/latest_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 12, 'INSUFFICIENT_WALKFORWARD': 2}
- us/balanced_blend/first_eligible_entry_open: {'INSUFFICIENT_WALKFORWARD': 2, 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 12}
- us/balanced_blend/latest_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 14}
- us/trend_family/first_eligible_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 10, 'INSUFFICIENT_WALKFORWARD': 4}
- us/trend_family/latest_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 12, 'INSUFFICIENT_WALKFORWARD': 2}
- tsx/compression_family/first_eligible_entry_open: {'INSUFFICIENT_CALIBRATION': 1, 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 12, 'INSUFFICIENT_WALKFORWARD': 8}
- tsx/compression_family/latest_entry_open: {'INSUFFICIENT_CALIBRATION': 1, 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 13, 'INSUFFICIENT_WALKFORWARD': 7}
- tsx/balanced_blend/first_eligible_entry_open: {'INSUFFICIENT_CALIBRATION': 1, 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 12, 'INSUFFICIENT_WALKFORWARD': 8}
- tsx/balanced_blend/latest_entry_open: {'INSUFFICIENT_CALIBRATION': 1, 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 13, 'INSUFFICIENT_WALKFORWARD': 7}
- tsx/trend_family/first_eligible_entry_open: {'INSUFFICIENT_CALIBRATION': 1, 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 14, 'INSUFFICIENT_WALKFORWARD': 6}
- tsx/trend_family/latest_entry_open: {'INSUFFICIENT_CALIBRATION': 1, 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 15, 'INSUFFICIENT_WALKFORWARD': 5}
