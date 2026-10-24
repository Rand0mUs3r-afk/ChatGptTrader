"""Validated Yahoo OHLC; re-fetch bad recent bars, never invent or drop prices."""
import time
import numpy as np
import pandas as pd

PRICE_BASIS = "Yahoo OHLC with auto_adjust=False; Adj Close not used; cash dividends not included in returns"
OHLCV = ("Open","High","Low","Close","Volume")


def describe(raw):
    if raw is None:
        return "provider returned None"
    missing = [c for c in OHLCV if c not in raw]
    if raw.empty or missing:
        return f"rows={len(raw)}; missing_columns={missing}"
    values = raw[list(OHLCV)].apply(pd.to_numeric,errors="coerce")
    bad = ~np.isfinite(values.to_numpy(dtype=float))
    counts = {str(c):int(bad[:,i].sum()) for i,c in enumerate(values.columns) if bad[:,i].any()}
    dates = [str(d) for d in values.index[bad.any(axis=1)][:5]]
    adj_bad = int(pd.to_numeric(raw["Adj Close"],errors="coerce").isna().sum()) if "Adj Close" in raw else "not returned"
    return f"rows={len(raw)}; nonfinite_by_column={counts}; first_bad_dates={dates}; unused_adj_close_missing={adj_bad}"


def recent_bad_dates(raw,cutoff):
    if raw is None or raw.empty or any(c not in raw for c in OHLCV):
        return []
    dates = pd.DatetimeIndex(raw.index).tz_localize(None).normalize()
    if not dates.is_unique:
        raise ValueError("Duplicate daily dates")
    bad = ~np.isfinite(raw[list(OHLCV)].apply(pd.to_numeric,errors="coerce").to_numpy(dtype=float)).all(axis=1)
    end = pd.Timestamp(cutoff).tz_localize(None).normalize()
    if bad.any() and ((dates[bad]<end-pd.Timedelta(days=45)).any() or (dates[bad]>=end).any()):
        raise ValueError("Nonfinite bar outside recent completed-date window; refusing truncation")
    return list(dates[bad])


def replace_recent_bars(raw,fresh,cutoff):
    bad_dates = recent_bad_dates(raw,cutoff)
    if not bad_dates:
        return raw.copy()
    if fresh is None or fresh.empty or any(c not in fresh for c in OHLCV):
        raise ValueError("Recent refetch lacks required OHLCV")
    fresh_dates = pd.DatetimeIndex(fresh.index).tz_localize(None).normalize()
    raw_dates = pd.DatetimeIndex(raw.index).tz_localize(None).normalize()
    if not fresh_dates.is_unique:
        raise ValueError("Duplicate refetched daily dates")
    repaired = raw.copy()
    for date in bad_dates:
        if date not in fresh_dates:
            raise ValueError(f"Recent refetch missing {date.date()}")
        bar = pd.to_numeric(fresh.iloc[int(fresh_dates.get_loc(date))][list(OHLCV)],errors="coerce").to_numpy(dtype=float)
        o,h,l,c,v = bar
        if not np.isfinite(bar).all() or min(o,h,l,c)<=0 or v<0 or l>min(o,c) or h<max(o,c) or l>h:
            raise ValueError(f"Recent refetch still invalid for {date.date()}")
        repaired.loc[raw.index[int(raw_dates.get_loc(date))],list(OHLCV)] = bar
    repaired.attrs["recent_bar_refetch"] = [str(d.date()) for d in bad_dates]
    return repaired


def fetch_daily(ticker, start, cutoff, required, fetcher=None, validator=None, sleeper=time.sleep, tail_fetcher=None):
    if validator is None:
        from run_recent_blend import prepare
        validator = prepare
    kwargs = dict(start=str(pd.Timestamp(start).date()),end=str(pd.Timestamp(cutoff).date()),
                  interval="1d",auto_adjust=False,actions=False)
    if fetcher is None:
        import yfinance as yf
        debug = getattr(getattr(yf,"config",None),"debug",None)
        if debug is not None and hasattr(debug,"hide_exceptions"):
            debug.hide_exceptions = False
        else:
            kwargs["raise_errors"] = True
        fetcher = lambda: yf.Ticker(ticker).history(**kwargs)
        if tail_fetcher is None:
            tail_fetcher = lambda recent_start: yf.Ticker(ticker).history(**dict(kwargs,start=str(pd.Timestamp(recent_start).date())))
    last_error, details = None, "no response"
    for attempt in range(1,4):
        print(f"Fetching {ticker}: attempt {attempt}/3; start={kwargs['start']}; end_exclusive={kwargs['end']}; auto_adjust=False",flush=True)
        details = "no response"
        try:
            raw = fetcher()
            details = describe(raw)
            if tail_fetcher is not None and recent_bad_dates(raw,cutoff):
                recent_start = max(pd.Timestamp(start),pd.Timestamp(cutoff)-pd.Timedelta(days=45))
                print(f"Re-fetching {ticker} recent daily OHLCV: start={recent_start.date()}; end_exclusive={kwargs['end']}; auto_adjust=False",flush=True)
                raw = replace_recent_bars(raw,tail_fetcher(recent_start),cutoff)
                details = describe(raw)
            frame = validator(raw,cutoff)
            if len(frame) < len(required) or not frame.index[-len(required):].equals(required):
                raise ValueError("Missing/stale expected exchange sessions")
            frame.attrs["price_basis"] = PRICE_BASIS
            frame.attrs["recent_bar_refetch"] = list(raw.attrs.get("recent_bar_refetch",[]))
            print(f"Validated {ticker}: {details}; refetched_dates={frame.attrs['recent_bar_refetch']}; {PRICE_BASIS}",flush=True)
            return frame
        except Exception as exc:
            last_error = exc
            print(f"Data failure {ticker}: {type(exc).__name__}: {exc}; {details}",flush=True)
            if attempt < 3:
                sleeper(2**attempt)
    raise RuntimeError(f"{ticker}: daily data failed after 3 attempts; "
                       f"{type(last_error).__name__}: {last_error}; {details}; "
                       "no prices filled, no ticker skipped") from last_error
