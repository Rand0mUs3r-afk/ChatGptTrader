# TSX universe and fractional research sizing

The prospective TSX scan list now contains the original 10 stocks, seven selected recent gainers, and four ETFs. The gainers snapshot is dated October 21, 2026, not a live ranking. It is not refreshed automatically. BB.TO was already included. CDRs and non-TSX listings were not added.

Mover source: https://www.marketinout.com/stock-screener/top-gainers/canada
ETF source: https://www.vanguard.ca/content/dam/intl/americas/canada/en/documents/vanguard-products-at-a-glance-en.pdf

Set FRACTIONAL_SHARES=true to opt into 0.001-share simulated sizing with minimum modeled notional 1 in the selected currency. Whole-share mode remains the library default. Allocation remains capped at 25% of equity, and planned stop risk at 1.5% of equity, including configured slippage. No RR or historical-evidence filters are relaxed.

This is not broker execution support. Fractional eligibility, quantity precision and protective-order handling must be verified with the actual broker. Fractional SL/TP fills remain theoretical model assumptions.

The pinned October backtest remains a whole-share baseline. Its integer share cast and less-than-one-share rejection must be updated before any fractional backtest is claimed. A frozen original TSX list is saved in config/tickers_tsx_october_baseline.txt for a future controlled sizing comparison; today's selected gainers must not be retrospectively treated as an October 1 selection.
