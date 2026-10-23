"""Bounded OHLCV retries with explicit diagnostics; never fill or drop bad prices."""
import time
import numpy as np
import pandas as pd


def describe(raw):
    if raw is None:
        return "provider returned None"
    missing = [c for c in ("Open","High","Low","Close","Volume") if c not in raw]
    if raw.empty or missing:
        return f"rows={len(raw)}; missing_columns={missing}"
    values = raw[["Open","High","Low","Close","Volume"]].apply(pd.to_numeric,errors="coerce")
    bad = ~np.isfinite(values.to_numpy(dtype=float))
    counts = {str(c):int(bad[:,i].sum()) for i,c in enumerate(values.columns) if bad[:,i].any()}
    dates = [str(d) for d in values.index[bad.any(axis=1)][:5]]
    return f"rows={len(raw)}; nonfinite_by_column={counts}; first_bad_dates={dates}"


def fetch_daily(ticker, start, cutoff, required, fetcher=None, validator=None, sleeper=time.sleep):
    if validator is None:
        from run_recent_blend import prepare
        validator = prepare
    kwargs = dict(start=str(pd.Timestamp(start).date()),end=str(pd.Timestamp(cutoff).date()),
                  interval="1d",auto_adjust=True,actions=False)
    if fetcher is None:
        import yfinance as yf
        debug = getattr(getattr(yf,"config",None),"debug",None)
        if debug is not None and hasattr(debug,"hide_exceptions"):
            debug.hide_exceptions = False
        else:
            kwargs["raise_errors"] = True
        fetcher = lambda: yf.Ticker(ticker).history(**kwargs)
    last_error, details = None, "no response"
    for attempt in range(1,4):
        print(f"Fetching {ticker}: attempt {attempt}/3; start={kwargs['start']}; end_exclusive={kwargs['end']}",flush=True)
        details = "no response"
        try:
            raw = fetcher()
            details = describe(raw)
            frame = validator(raw,cutoff)
            if len(frame) < len(required) or not frame.index[-len(required):].equals(required):
                raise ValueError("Missing/stale expected exchange sessions")
            print(f"Validated {ticker}: {details}",flush=True)
            return frame
        except Exception as exc:
            last_error = exc
            print(f"Data failure {ticker}: {type(exc).__name__}: {exc}; {details}",flush=True)
            if attempt < 3:
                sleeper(2**attempt)
    raise RuntimeError(f"{ticker}: daily data failed after 3 attempts; "
                       f"{type(last_error).__name__}: {last_error}; {details}; "
                       "no prices filled, no ticker skipped") from last_error
