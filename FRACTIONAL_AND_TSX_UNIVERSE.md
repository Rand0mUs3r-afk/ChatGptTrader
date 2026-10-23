# TSX universe and fractional research sizing

The prospective TSX scan list contains the original 10 stocks, seven selected recent gainers, and four ETFs. The gainers snapshot is dated October 21, 2026, not a live ranking, and is not automatically refreshed. BB.TO was already included.

Mover source: https://www.marketinout.com/stock-screener/top-gainers/canada
ETF source: https://www.vanguard.ca/content/dam/intl/americas/canada/en/documents/vanguard-products-at-a-glance-en.pdf

Latest scans support FRACTIONAL_SHARES=true. The corrected October-only runner supports --share-mode fractional (default) or --share-mode whole. Fractions use 0.001-share increments, minimum modeled notional 1 in the selected currency, a 25% allocation cap and 1.5% equity planned-stop-risk cap including slippage. Quantity is never cast back to an integer or rejected merely for being less than one share. No RR/evidence filters are relaxed. Broker eligibility, precision and protective-order execution remain unverified assumptions; no orders are placed.

Existing whole-share results are preserved. October performance includes only October entries through the latest completed October session; earlier bars are training-only and unclosed positions remain separate. The original TSX universe is recorded in config/tickers_tsx_october_baseline.txt. Newly selected movers and ETFs cannot enter before October 23, 2026, as recorded in config/tsx_added_eligibility.csv. Therefore they do not contribute to a backtest ending October 22. Original-universe/development-sample bias still applies; this is not independent validation.
