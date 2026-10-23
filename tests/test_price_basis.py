import ast
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from checked_history import fetch_daily, PRICE_BASIS


def test_valid_ohlc_survives_missing_adjusted_close(monkeypatch):
    raw = pd.DataFrame({'Open':[100.0]*20,'High':[102.0]*20,'Low':[99.0]*20,'Close':[101.0]*20,'Adj Close':[101.0]*19+[np.nan],'Volume':[1000]*20},index=pd.bdate_range('2026-09-25',periods=20))
    calls = []
    def history(**kwargs):
        calls.append(kwargs)
        return raw.copy()
    fake = SimpleNamespace(Ticker=lambda _:SimpleNamespace(history=history),config=SimpleNamespace(debug=SimpleNamespace(hide_exceptions=True)))
    monkeypatch.setitem(sys.modules,'yfinance',fake)
    result = fetch_daily('AAPL','2026-09-25','2026-10-23',raw.index,sleeper=lambda _:None)
    assert calls[0]['auto_adjust'] is False
    assert result.Close.iloc[-1] == 101
    assert np.isfinite(result.to_numpy()).all()
    assert pd.isna(raw['Adj Close'].iloc[-1])
    assert result.attrs['price_basis'] == PRICE_BASIS


def test_five_year_download_uses_same_basis():
    source = Path(__file__).resolve().parents[1]/'assess_targets.py'
    flags = [kw.value for node in ast.walk(ast.parse(source.read_text())) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr == 'history' for kw in node.keywords if kw.arg == 'auto_adjust']
    assert flags
    assert all(isinstance(flag,ast.Constant) and flag.value is False for flag in flags)
