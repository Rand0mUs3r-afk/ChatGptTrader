"""Strict requested-window history and pre-entry feasibility for the 45-session lab."""
import numpy as np
import pandas as pd


def prepare_window(raw,cutoff,start):
    columns = ["Open","High","Low","Close","Volume"]
    frame = raw[columns].copy()
    frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    if frame.index.has_duplicates or frame.index.hasnans:
        raise ValueError("Duplicate or invalid sessions")
    start = pd.Timestamp(start).tz_localize(None).normalize()
    cutoff = pd.Timestamp(cutoff).tz_localize(None).normalize()
    if start>=cutoff:
        raise ValueError("Invalid requested window")
    frame = frame.sort_index().loc[lambda x:(x.index>=start)&(x.index<cutoff)]
    frame = frame.apply(pd.to_numeric,errors="raise")
    if frame.empty or not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError("Empty or nonfinite data")
    if ((frame[["Open","High","Low","Close"]]<=0).any().any() or (frame.Volume<0).any()
        or (frame.Low>frame[["Open","Close"]].min(axis=1)).any()
        or (frame.High<frame[["Open","Close"]].max(axis=1)).any()):
        raise ValueError("Invalid OHLCV")
    return frame


def fetch_daily(ticker,start,cutoff,required,**kwargs):
    from checked_history import fetch_daily as checked_fetch
    if "validator" in kwargs:
        raise ValueError("45-session window validator cannot be overridden")
    return checked_fetch(ticker,start,cutoff,required,
        validator=lambda raw,end:prepare_window(raw,end,start),**kwargs)


def sample_feasibility(records,known_bars):
    from october_15_session import MIN_TRAIN,MIN_WF,TRAIN_WINDOW,best_target
    if known_bars<0:
        raise ValueError("Invalid known-bar count")
    past = [r for r in records if r["end_index"]<known_bars]
    forward = sum(best_target(past[max(0,k-TRAIN_WINDOW):k])[1]>0 for k in range(MIN_TRAIN,len(past)))
    status = "INSUFFICIENT_CALIBRATION" if len(past)<MIN_TRAIN else "INSUFFICIENT_WALKFORWARD" if forward<MIN_WF else "SAMPLE_COUNTS_FEASIBLE_NOT_TRADE_APPROVAL"
    return dict(known_bars=int(known_bars),max_possible_nonoverlapping_examples=max(0,(known_bars-51)//45),
        matured_calibration_examples=len(past),maximum_walkforward_examples=max(0,len(past)-MIN_TRAIN),
        qualifying_walkforward_examples=int(forward),required_calibration_examples=MIN_TRAIN,
        required_walkforward_examples=MIN_WF,sample_feasibility=status)
