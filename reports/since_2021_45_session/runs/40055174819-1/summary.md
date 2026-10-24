# Entries since 2021 - maximum 45 trading sessions

2021-ONWARD RESEARCH, entries from January 1, 2021 through the latest completed exchange session available at execution. Any eligible trading session may supply an entry when prior-close strategy rules pass; there is no Monday, month, anniversary or October-only restriction. This does not force a trade every day. Maximum 45 TRADING SESSIONS, entry is session one; SL/TP may exit earlier. One position at a time per independent scenario, no same-day reentry. Accounts compound across calendar years; positions carry across year boundaries. Calendar-year returns use marked equity, not reset accounts; the final year may be incomplete. Only pre-entry signals and matured outcomes inform decisions. Request ten years of pre-2021 history from 2011, retain all available requested bars, and disclose actual coverage and sample feasibility. Preserve 20 calibration/10 qualifying walk-forward minimums, positive-edge checks, 30-example training window, raw-R target grid and original pattern stops. Insufficient evidence is not a trade. Use the current source watchlist without AMD or AMZN; this is a retrospective full-period cohort study, not a reconstructed point-in-time historical universe. The inherited loader requires at least 60 pre-January-2021 sessions; later-listed names failing that criterion are excluded from the whole study and listed in universe exclusions, not padded with invented prices. Known later TSX selections retain recorded eligibility dates, not January 2021. Compression/balanced/trend-family signals, empirical targets and labeled fixed-2R controls. Separate USD/CAD accounts, fractional sizing by default, 25% allocation and 1.5% planned equity-risk caps, 15 bps/side, zero commissions/dividend cash; gaps may exceed planned risk. Daily stop-first fills, broker fractional execution unverified, current-universe and development-sample bias; historical hit rates are not forecast probabilities. Open positions remain marked and unclassified as wins/losses. Zero-entry scenarios are not evaluable. Do not sum independent scenarios as a portfolio. Previous October and 2026-YTD outputs remain untouched. No orders or live strategy promotion.

## Full-period results

```text
market          variant           strategy       asof  entries  closed_trades  wins  losses  open_positions  ending_marked_equity  total_return_pct  max_marked_drawdown_pct        activity_status
    us        empirical compression_family 2026-10-23      111            111    41      70               0            903.747229         -9.625277                15.072747 RESEARCH_NOT_VALIDATED
    us fixed_2r_control compression_family 2026-10-23      111            111    50      61               0           1243.209739         24.320974                 8.068709 RESEARCH_NOT_VALIDATED
    us        empirical     balanced_blend 2026-10-23      113            112    50      62               1           1005.007292          0.500729                12.873996 RESEARCH_NOT_VALIDATED
    us fixed_2r_control     balanced_blend 2026-10-23      124            123    46      77               1            864.164545        -13.583546                23.291311 RESEARCH_NOT_VALIDATED
    us        empirical       trend_family 2026-10-23      119            118    48      70               1           1109.107392         10.910739                11.895148 RESEARCH_NOT_VALIDATED
    us fixed_2r_control       trend_family 2026-10-23      131            131    51      80               0           1073.021128          7.302113                13.659619 RESEARCH_NOT_VALIDATED
   tsx        empirical compression_family 2026-10-23      124            123    58      65               1           1308.319137         30.831914                13.084731 RESEARCH_NOT_VALIDATED
   tsx fixed_2r_control compression_family 2026-10-23      142            141    50      91               1           1017.121912          1.712191                21.168873 RESEARCH_NOT_VALIDATED
   tsx        empirical     balanced_blend 2026-10-23      145            145    70      75               0           1166.186032         16.618603                15.271050 RESEARCH_NOT_VALIDATED
   tsx fixed_2r_control     balanced_blend 2026-10-23      120            119    45      74               1           1076.999434          7.699943                 9.943659 RESEARCH_NOT_VALIDATED
   tsx        empirical       trend_family 2026-10-23       94             93    45      48               1           1301.399424         30.139942                17.003785 RESEARCH_NOT_VALIDATED
   tsx fixed_2r_control       trend_family 2026-10-23      130            129    59      70               1           1357.623324         35.762332                19.618808 RESEARCH_NOT_VALIDATED
```

## Calendar-year results (continuous accounts, no annual reset)

```text
market currency          variant           strategy  year first_session last_session  starting_marked_equity  ending_marked_equity  marked_pnl  return_pct  within_year_drawdown_pct  entries  closed_trades  wins  losses
    us      USD        empirical compression_family  2021    2021-01-04   2021-12-31             1000.000000            976.940621  -23.059379   -2.305938                  4.841092       15             15     5      10
    us      USD        empirical compression_family  2022    2022-01-03   2022-12-30              976.940621            901.216822  -75.723798   -7.751116                 12.414962       23             22     5      17
    us      USD        empirical compression_family  2023    2023-01-03   2023-12-29              901.216822            915.314218   14.097396    1.564262                  6.648587       20             21     8      13
    us      USD        empirical compression_family  2024    2024-01-02   2024-12-31              915.314218            914.559639   -0.754579   -0.082439                  4.508599       20             20     8      12
    us      USD        empirical compression_family  2025    2025-01-02   2025-12-31              914.559639            881.043522  -33.516117   -3.664727                  7.223594       21             20     8      12
    us      USD        empirical compression_family  2026    2026-01-02   2026-10-23              881.043522            903.747229   22.703706    2.576911                  4.032339       12             13     7       6
    us      USD fixed_2r_control compression_family  2021    2021-01-04   2021-12-31             1000.000000            988.745080  -11.254920   -1.125492                  6.042286       24             23     7      16
    us      USD fixed_2r_control compression_family  2022    2022-01-03   2022-12-30              988.745080            971.340356  -17.404724   -1.760284                  7.403876       19             19     6      13
    us      USD fixed_2r_control compression_family  2023    2023-01-03   2023-12-29              971.340356           1107.142560  135.802203   13.980908                  2.771892       21             21    14       7
    us      USD fixed_2r_control compression_family  2024    2024-01-02   2024-12-31             1107.142560           1091.074900  -16.067660   -1.451273                  3.512830       15             16     6      10
    us      USD fixed_2r_control compression_family  2025    2025-01-02   2025-12-31             1091.074900           1169.626423   78.551523    7.199462                  5.529443       17             16     9       7
    us      USD fixed_2r_control compression_family  2026    2026-01-02   2026-10-23             1169.626423           1243.209739   73.583316    6.291181                  2.767682       15             16     8       8
    us      USD        empirical     balanced_blend  2021    2021-01-04   2021-12-31             1000.000000           1045.725953   45.725953    4.572595                  3.290968       20             20    11       9
    us      USD        empirical     balanced_blend  2022    2022-01-03   2022-12-30             1045.725953            989.413804  -56.312149   -5.384982                  8.128345       15             15     4      11
    us      USD        empirical     balanced_blend  2023    2023-01-03   2023-12-29              989.413804            997.960364    8.546560    0.863800                  6.397237       21             20    11       9
    us      USD        empirical     balanced_blend  2024    2024-01-02   2024-12-31              997.960364           1045.636986   47.676622    4.777406                  6.038185       15             15     9       6
    us      USD        empirical     balanced_blend  2025    2025-01-02   2025-12-31             1045.636986           1026.216914  -19.420072   -1.857248                 10.610777       21             21     8      13
    us      USD        empirical     balanced_blend  2026    2026-01-02   2026-10-23             1026.216914           1005.007292  -21.209622   -2.066778                  4.629287       21             21     7      14
    us      USD fixed_2r_control     balanced_blend  2021    2021-01-04   2021-12-31             1000.000000            934.289920  -65.710080   -6.571008                  8.544754       23             22     6      16
    us      USD fixed_2r_control     balanced_blend  2022    2022-01-03   2022-12-30              934.289920            792.286886 -142.003034  -15.199033                 16.875028       20             20     3      17
    us      USD fixed_2r_control     balanced_blend  2023    2023-01-03   2023-12-29              792.286886            853.309804   61.022918    7.702124                  2.550586       15             15    10       5
    us      USD fixed_2r_control     balanced_blend  2024    2024-01-02   2024-12-31              853.309804            844.542357   -8.767447   -1.027463                  7.966851       30             30    12      18
    us      USD fixed_2r_control     balanced_blend  2025    2025-01-02   2025-12-31              844.542357            890.948902   46.406544    5.494875                  6.215806       22             22    10      12
    us      USD fixed_2r_control     balanced_blend  2026    2026-01-02   2026-10-23              890.948902            864.164545  -26.784357   -3.006273                  5.788859       14             14     5       9
    us      USD        empirical       trend_family  2021    2021-01-04   2021-12-31             1000.000000           1083.128166   83.128166    8.312817                  5.149326       18             17    11       6
    us      USD        empirical       trend_family  2022    2022-01-03   2022-12-30             1083.128166            967.912127 -115.216039  -10.637341                 11.492452       25             26     5      21
    us      USD        empirical       trend_family  2023    2023-01-03   2023-12-29              967.912127           1094.512161  126.600034   13.079703                  3.169441       17             16    10       6
    us      USD        empirical       trend_family  2024    2024-01-02   2024-12-31             1094.512161           1140.678221   46.166060    4.217958                  3.606237       16             16     8       8
    us      USD        empirical       trend_family  2025    2025-01-02   2025-12-31             1140.678221           1072.088230  -68.589991   -6.013089                  9.001291       25             25     5      20
    us      USD        empirical       trend_family  2026    2026-01-02   2026-10-23             1072.088230           1109.107392   37.019162    3.452996                  5.074778       18             18     9       9
    us      USD fixed_2r_control       trend_family  2021    2021-01-04   2021-12-31             1000.000000           1034.267305   34.267305    3.426731                  4.091686       20             19     8      11
    us      USD fixed_2r_control       trend_family  2022    2022-01-03   2022-12-30             1034.267305           1022.635376  -11.631930   -1.124654                  8.891191       22             22     6      16
    us      USD fixed_2r_control       trend_family  2023    2023-01-03   2023-12-29             1022.635376           1140.886971  118.251595   11.563417                  3.323511       17             17    11       6
    us      USD fixed_2r_control       trend_family  2024    2024-01-02   2024-12-31             1140.886971           1130.792963  -10.094008   -0.884751                  4.810725       23             23     9      14
    us      USD fixed_2r_control       trend_family  2025    2025-01-02   2025-12-31             1130.792963           1217.566767   86.773804    7.673713                  5.803501       21             21    10      11
    us      USD fixed_2r_control       trend_family  2026    2026-01-02   2026-10-23             1217.566767           1073.021128 -144.545638  -11.871681                 13.659619       28             29     7      22
   tsx      CAD        empirical compression_family  2021    2021-01-04   2021-12-31             1000.000000           1052.687747   52.687747    5.268775                  3.756398       16             15     7       8
   tsx      CAD        empirical compression_family  2022    2022-01-04   2022-12-30             1052.687747           1183.924912  131.237165   12.466865                  5.642090       22             22    13       9
   tsx      CAD        empirical compression_family  2023    2023-01-03   2023-12-29             1183.924912           1123.643696  -60.281216   -5.091642                  6.316122       20             20     6      14
   tsx      CAD        empirical compression_family  2024    2024-01-02   2024-12-31             1123.643696           1114.514278   -9.129418   -0.812483                  7.804826       26             26    11      15
   tsx      CAD        empirical compression_family  2025    2025-01-02   2025-12-31             1114.514278           1203.376657   88.862379    7.973193                  5.752710       22             22    11      11
   tsx      CAD        empirical compression_family  2026    2026-01-02   2026-10-23             1203.376657           1308.319137  104.942480    8.720668                  5.983318       18             18    10       8
   tsx      CAD fixed_2r_control compression_family  2021    2021-01-04   2021-12-31             1000.000000            927.125668  -72.874332   -7.287433                 12.786019       33             32    10      22
   tsx      CAD fixed_2r_control compression_family  2022    2022-01-04   2022-12-30              927.125668            842.010565  -85.115103   -9.180536                 12.616830       25             25     7      18
   tsx      CAD fixed_2r_control compression_family  2023    2023-01-03   2023-12-29              842.010565            911.042271   69.031706    8.198437                  4.625136       19             19     8      11
   tsx      CAD fixed_2r_control compression_family  2024    2024-01-02   2024-12-31              911.042271            967.015029   55.972758    6.143816                  5.657324       23             23    10      13
   tsx      CAD fixed_2r_control compression_family  2025    2025-01-02   2025-12-31              967.015029            989.467025   22.451997    2.321784                  6.069640       25             25     9      16
   tsx      CAD fixed_2r_control compression_family  2026    2026-01-02   2026-10-23              989.467025           1017.121912   27.654886    2.794928                  6.562011       17             17     6      11
   tsx      CAD        empirical     balanced_blend  2021    2021-01-04   2021-12-31             1000.000000           1116.612030  116.612030   11.661203                  2.899736       12             11     7       4
   tsx      CAD        empirical     balanced_blend  2022    2022-01-04   2022-12-30             1116.612030           1169.761525   53.149495    4.759889                  6.544423       21             21     8      13
   tsx      CAD        empirical     balanced_blend  2023    2023-01-03   2023-12-29             1169.761525           1046.721840 -123.039685  -10.518356                 12.806897       36             36    11      25
   tsx      CAD        empirical     balanced_blend  2024    2024-01-02   2024-12-31             1046.721840           1107.284322   60.562482    5.785919                  2.570726       29             29    19      10
   tsx      CAD        empirical     balanced_blend  2025    2025-01-02   2025-12-31             1107.284322           1082.603060  -24.681262   -2.228990                  6.618556       35             35    16      19
   tsx      CAD        empirical     balanced_blend  2026    2026-01-02   2026-10-23             1082.603060           1166.186032   83.582972    7.720556                  4.480929       12             13     9       4
   tsx      CAD fixed_2r_control     balanced_blend  2021    2021-01-04   2021-12-31             1000.000000           1090.258787   90.258787    9.025879                  3.507761       13             12     7       5
   tsx      CAD fixed_2r_control     balanced_blend  2022    2022-01-04   2022-12-30             1090.258787           1019.249454  -71.009332   -6.513071                  9.390598       23             23     7      16
   tsx      CAD fixed_2r_control     balanced_blend  2023    2023-01-03   2023-12-29             1019.249454           1077.865711   58.616257    5.750924                  3.899916       21             21     9      12
   tsx      CAD fixed_2r_control     balanced_blend  2024    2024-01-02   2024-12-31             1077.865711           1083.701997    5.836286    0.541467                  9.180115       24             24     7      17
   tsx      CAD fixed_2r_control     balanced_blend  2025    2025-01-02   2025-12-31             1083.701997           1082.493515   -1.208482   -0.111514                  7.411708       16             17     7      10
   tsx      CAD fixed_2r_control     balanced_blend  2026    2026-01-02   2026-10-23             1082.493515           1076.999434   -5.494081   -0.507539                  6.236468       23             22     8      14
   tsx      CAD        empirical       trend_family  2021    2021-01-04   2021-12-31             1000.000000           1304.240772  304.240772   30.424077                  3.736904       20             19    13       6
   tsx      CAD        empirical       trend_family  2022    2022-01-04   2022-12-30             1304.240772           1337.876420   33.635649    2.578945                  3.921102       11             11     5       6
   tsx      CAD        empirical       trend_family  2023    2023-01-03   2023-12-29             1337.876420           1291.536677  -46.339744   -3.463679                  6.806585       12             13     4       9
   tsx      CAD        empirical       trend_family  2024    2024-01-02   2024-12-31             1291.536677           1308.041628   16.504951    1.277931                  6.293676       12             11     5       6
   tsx      CAD        empirical       trend_family  2025    2025-01-02   2025-12-31             1308.041628           1281.488433  -26.553194   -2.029996                 13.412116       17             17     9       8
   tsx      CAD        empirical       trend_family  2026    2026-01-02   2026-10-23             1281.488433           1301.399424   19.910990    1.553739                  9.092092       22             22     9      13
   tsx      CAD fixed_2r_control       trend_family  2021    2021-01-04   2021-12-31             1000.000000           1125.796214  125.796214   12.579621                  6.939272       24             23    11      12
   tsx      CAD fixed_2r_control       trend_family  2022    2022-01-04   2022-12-30             1125.796214           1168.665419   42.869205    3.807901                  4.994219       22             22     9      13
   tsx      CAD fixed_2r_control       trend_family  2023    2023-01-03   2023-12-29             1168.665419           1198.383489   29.718071    2.542907                  8.399161       24             24    10      14
   tsx      CAD fixed_2r_control       trend_family  2024    2024-01-02   2024-12-31             1198.383489           1382.669384  184.285895   15.377873                  4.588918       23             23    13      10
   tsx      CAD fixed_2r_control       trend_family  2025    2025-01-02   2025-12-31             1382.669384           1217.286919 -165.382465  -11.961100                 18.532008       26             26     9      17
   tsx      CAD fixed_2r_control       trend_family  2026    2026-01-02   2026-10-23             1217.286919           1357.623324  140.336405   11.528622                  2.654359       11             11     7       4
```

## Pre-entry sample feasibility (not trade approval)

- us/compression_family/first_eligible_entry_open: {'INSUFFICIENT_WALKFORWARD': 4, 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 10}
- us/compression_family/latest_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 13, 'INSUFFICIENT_WALKFORWARD': 1}
- us/balanced_blend/first_eligible_entry_open: {'INSUFFICIENT_WALKFORWARD': 5, 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 9}
- us/balanced_blend/latest_entry_open: {'INSUFFICIENT_WALKFORWARD': 1, 'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 13}
- us/trend_family/first_eligible_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 8, 'INSUFFICIENT_WALKFORWARD': 6}
- us/trend_family/latest_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 14}
- tsx/compression_family/first_eligible_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 12, 'INSUFFICIENT_WALKFORWARD': 6}
- tsx/compression_family/latest_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 15, 'INSUFFICIENT_WALKFORWARD': 3}
- tsx/balanced_blend/first_eligible_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 16, 'INSUFFICIENT_WALKFORWARD': 2}
- tsx/balanced_blend/latest_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 16, 'INSUFFICIENT_WALKFORWARD': 2}
- tsx/trend_family/first_eligible_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 11, 'INSUFFICIENT_WALKFORWARD': 7}
- tsx/trend_family/latest_entry_open: {'SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL': 16, 'INSUFFICIENT_WALKFORWARD': 2}
