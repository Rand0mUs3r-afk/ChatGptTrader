# October entries - maximum 15 sessions (fractional)

EXPERIMENTAL OCTOBER-ENTRY RESEARCH, maximum 15 TRADING SESSIONS, counting entry as session one; SL/TP may exit sooner. October performance ends at the latest completed October session; later exits are not fabricated. Most recent entries may lack a complete 15-session outcome; open positions and full-horizon maturity are shown separately. Earlier bars are calibration-only. Portfolio dates are aligned, but calibration keeps each ticker's full available history, including for shorter-listed names. Compression and balanced blend retain original pattern stops; trend_family is an alternative trend/momentum-family signal, not a new SMA-pullback strategy. Stops are never tightened merely to improve RR. Empirical targets test the predefined raw-R grid [0.5,0.75,1,1.25,1.5,2] on nonoverlapping same-stock/same-strategy examples. At least 20 matured examples are needed; select the highest mean net R from at most 30 earlier examples, breaking ties toward the lower target. Each historical walk-forward selection uses only its earlier completed examples. Require at least 10 positive-training-edge walk-forward entries and positive mean walk-forward net R. Current target must cover modeled costs; there is NO unconditional 1.25 RR floor in empirical mode. Nearest confirmed resistance is a warning, not an automatic hard cap. These are fixed research choices, not validated optimal parameters. Historical hit rates and standard errors are descriptive, NOT calibrated future probabilities or guaranteed exits. The fixed-2R control is an unvalidated reference with its original 1.25 net-RR gate and no historical gates. Same universe dates, ranking, fractional assumptions, 25% allocation cap, 1.5% equity planned-risk cap and 15 bps/side. No commissions/dividend cash; daily stop-first and gap-risk assumptions; broker fractional protective orders unverified. Separate accounts, no FX pooling, no orders, no automatic strategy promotion. Current-universe/development-sample bias remains; original 5/7-session results stay preserved.

| Market | Target model | Strategy | Entries | Closed | Won | Lost | Open | Full-horizon mature | Realized P&L | Unrealized P&L | Equity | Return % | Drawdown % | Status |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| us (USD) | empirical | compression_family | 3 | 2 | 1 | 1 | 1 | 1 | 10.12 | -6.67 | 1003.45 | 0.34 | 2.50 | RESEARCH_NOT_VALIDATED |
| us (USD) | fixed_2r_control | compression_family | 2 | 2 | 1 | 1 | 0 | 1 | -1.84 | 0.00 | 998.16 | -0.18 | 2.28 | RESEARCH_NOT_VALIDATED |
| us (USD) | empirical | balanced_blend | 2 | 2 | 1 | 1 | 0 | 1 | 11.91 | 0.00 | 1011.91 | 1.19 | 1.88 | RESEARCH_NOT_VALIDATED |
| us (USD) | fixed_2r_control | balanced_blend | 2 | 1 | 1 | 0 | 1 | 1 | 9.91 | 3.89 | 1013.80 | 1.38 | 1.22 | RESEARCH_NOT_VALIDATED |
| us (USD) | empirical | trend_family | 5 | 4 | 1 | 3 | 1 | 2 | -27.66 | -6.43 | 965.92 | -3.41 | 3.94 | RESEARCH_NOT_VALIDATED |
| us (USD) | fixed_2r_control | trend_family | 4 | 4 | 1 | 3 | 0 | 1 | -6.78 | 0.00 | 993.22 | -0.68 | 2.46 | RESEARCH_NOT_VALIDATED |
| tsx (CAD) | empirical | compression_family | 1 | 1 | 0 | 1 | 0 | 1 | -6.79 | 0.00 | 993.21 | -0.68 | 1.85 | RESEARCH_NOT_VALIDATED |
| tsx (CAD) | fixed_2r_control | compression_family | 1 | 1 | 0 | 1 | 0 | 1 | -6.79 | 0.00 | 993.21 | -0.68 | 1.85 | RESEARCH_NOT_VALIDATED |
| tsx (CAD) | empirical | balanced_blend | 2 | 1 | 0 | 1 | 1 | 0 | -7.81 | 4.74 | 996.94 | -0.31 | 0.82 | RESEARCH_NOT_VALIDATED |
| tsx (CAD) | fixed_2r_control | balanced_blend | 2 | 1 | 0 | 1 | 1 | 1 | -6.79 | 1.75 | 994.96 | -0.50 | 1.85 | RESEARCH_NOT_VALIDATED |
| tsx (CAD) | empirical | trend_family | 2 | 1 | 0 | 1 | 1 | 1 | -6.79 | -10.32 | 982.89 | -1.71 | 2.37 | RESEARCH_NOT_VALIDATED |
| tsx (CAD) | fixed_2r_control | trend_family | 3 | 2 | 0 | 2 | 1 | 2 | -24.89 | 4.02 | 979.13 | -2.09 | 2.75 | RESEARCH_NOT_VALIDATED |

## Evaluated candidate decisions

- us / empirical / compression_family, as of 2026-10-23: {'EXPERIMENTAL_CANDIDATE': 3, 'INSUFFICIENT_WALKFORWARD': 2, 'SKIP_NO_CALIBRATION_EDGE': 1}
- us / fixed_2r_control / compression_family, as of 2026-10-23: {'EXPERIMENTAL_CANDIDATE': 2}
- us / empirical / balanced_blend, as of 2026-10-23: {'SKIP_NONPOSITIVE_WALKFORWARD': 1, 'SKIP_NO_CALIBRATION_EDGE': 4, 'EXPERIMENTAL_CANDIDATE': 2}
- us / fixed_2r_control / balanced_blend, as of 2026-10-23: {'EXPERIMENTAL_CANDIDATE': 2}
- us / empirical / trend_family, as of 2026-10-23: {'SKIP_NO_CALIBRATION_EDGE': 11, 'SKIP_NONPOSITIVE_WALKFORWARD': 1, 'EXPERIMENTAL_CANDIDATE': 5}
- us / fixed_2r_control / trend_family, as of 2026-10-23: {'EXPERIMENTAL_CANDIDATE': 4}
- tsx / empirical / compression_family, as of 2026-10-23: {'EXPERIMENTAL_CANDIDATE': 1}
- tsx / fixed_2r_control / compression_family, as of 2026-10-23: {'EXPERIMENTAL_CANDIDATE': 1}
- tsx / empirical / balanced_blend, as of 2026-10-23: {'SKIP_NONPOSITIVE_WALKFORWARD': 5, 'INSUFFICIENT_WALKFORWARD': 4, 'SKIP_NO_CALIBRATION_EDGE': 5, 'EXPERIMENTAL_CANDIDATE': 2}
- tsx / fixed_2r_control / balanced_blend, as of 2026-10-23: {'EXPERIMENTAL_CANDIDATE': 2}
- tsx / empirical / trend_family, as of 2026-10-23: {'SKIP_NONPOSITIVE_WALKFORWARD': 1, 'EXPERIMENTAL_CANDIDATE': 2, 'SKIP_NO_CALIBRATION_EDGE': 3, 'INSUFFICIENT_WALKFORWARD': 1}
- tsx / fixed_2r_control / trend_family, as of 2026-10-23: {'EXPERIMENTAL_CANDIDATE': 3, 'SKIP_LOW_NET_RR': 1}
