from unittest.mock import patch
import pytest
from alpaca_paper_readiness import readiness,read_account,NoRedirect,PAPER_ACCOUNT_URL

ACCOUNT="12345678-1234-4234-8234-123456789abc"
OTHER="87654321-4321-4321-8321-abcdef123456"


def account(**updates):
    return dict(id=ACCOUNT,status="ACTIVE",currency="USD",account_blocked=False,trading_blocked=False)|updates


def test_missing_expected_does_not_authorize():
    r=readiness(account(),"")
    assert r["account_id"]==ACCOUNT and not r["account_verified"] and not r["order_submission_enabled"]


def test_mismatch_and_invalid_expected():
    assert readiness(account(),OTHER)["reason"]=="ACCOUNT_ID_MISMATCH"
    assert readiness(account(),"not-an-account-id")["reason"]=="EXPECTED_ACCOUNT_ID_INVALID"


@pytest.mark.parametrize("updates",[dict(status="ONBOARDING"),dict(currency="CAD"),dict(account_blocked=True),dict(trading_blocked=True)])
def test_blocked_accounts_do_not_verify(updates):
    assert not readiness(account(**updates),ACCOUNT)["account_verified"]


def test_verified_account_still_cannot_trade():
    r=readiness(account(),ACCOUNT)
    assert r["account_verified"] and not r["order_submission_enabled"]


def test_credentials_rejected_before_network():
    with patch("urllib.request.build_opener") as network:
        with pytest.raises(ValueError): read_account("","")
        network.assert_not_called()


def test_only_paper_endpoint_and_no_redirect():
    assert PAPER_ACCOUNT_URL=="https://paper-api.alpaca.markets/v2/account"
    with pytest.raises(RuntimeError): NoRedirect().redirect_request(None,None,None,None,None,None)
