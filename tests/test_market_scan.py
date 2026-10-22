import pytest
from scan_market_setups import market_settings

def test_tsx_uses_toronto_calendar_and_cad():
    assert market_settings('tsx') == ('config/tickers_tsx.txt', 'XTSE', 'CAD')

def test_us_settings_unchanged():
    assert market_settings('us') == ('config/tickers.txt', 'XNYS', 'USD')

def test_unknown_market_rejected():
    with pytest.raises(ValueError):
        market_settings('unknown')
