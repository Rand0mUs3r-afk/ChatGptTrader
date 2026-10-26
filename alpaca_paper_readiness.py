"""Read-only paper account check; cannot submit, cancel or replace orders."""
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
from uuid import UUID

PAPER_ACCOUNT_URL = "https://paper-api.alpaca.markets/v2/account"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RuntimeError("Credential-bearing redirects are forbidden")


def read_account(key_id,secret_key):
    if not key_id or not secret_key:
        raise ValueError("Missing Alpaca paper credentials")
    request=urllib.request.Request(PAPER_ACCOUNT_URL,method="GET",headers={
        "APCA-API-KEY-ID":key_id,"APCA-API-SECRET-KEY":secret_key,"Accept":"application/json"})
    opener=urllib.request.build_opener(NoRedirect())
    with opener.open(request,timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def readiness(account,expected):
    account_id=str(UUID(str(account.get("id",""))))
    result=dict(account_id=account_id,status=str(account.get("status","")),currency=str(account.get("currency","")),
        account_verified=False,order_submission_enabled=False)
    if not expected.strip():
        return dict(**result,reason="EXPECTED_ACCOUNT_ID_NOT_SET")
    try:
        expected=str(UUID(expected.strip()))
    except ValueError:
        return dict(**result,reason="EXPECTED_ACCOUNT_ID_INVALID")
    if account_id!=expected:
        return dict(**result,reason="ACCOUNT_ID_MISMATCH")
    if result["status"]!="ACTIVE" or result["currency"]!="USD" or account.get("account_blocked",True) or account.get("trading_blocked",True):
        return dict(**result,reason="ACCOUNT_NOT_READY")
    result["account_verified"]=True
    return dict(**result,reason="READ_ONLY_ACCOUNT_VERIFIED")


def main():
    try:
        result=readiness(read_account(os.getenv("ALPACA_PAPER_KEY_ID",""),os.getenv("ALPACA_PAPER_SECRET_KEY","")),
            os.getenv("ALPACA_EXPECTED_PAPER_ACCOUNT_ID",""))
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Paper account check failed: HTTP {error.code}. Check paper credentials. No orders submitted.") from None
    except urllib.error.URLError:
        raise SystemExit("Paper account network request failed. No orders submitted.") from None
    except (ValueError,RuntimeError,KeyError,TypeError):
        raise SystemExit("Missing paper credentials, invalid account response or blocked redirect. No orders submitted.") from None
    print(json.dumps(result,indent=2))
    summary=os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        text=("# Alpaca paper account check - READ ONLY\n\nPaper account UUID (copy into ALPACA_EXPECTED_PAPER_ACCOUNT_ID):\n\n"
            +"```text\n"+result["account_id"]+"\n```\n\nStatus: "+result["status"]+"; currency: "+result["currency"]
            +"; result: "+result["reason"]+"\n\nOrder submission is unconditionally disabled in this check. Keep ALPACA_PAPER_ENABLED=false. "
            +"No S&P 500 import, execution worker, scheduling or order management is implemented by this check.\n")
        with Path(summary).open("a",encoding="utf-8") as out:
            out.write(text)


if __name__=="__main__":
    main()
