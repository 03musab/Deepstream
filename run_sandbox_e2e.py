"""run_sandbox_e2e.py — Cashfree sandbox end-to-end test harness.

Traces the full payment flow against a REAL Cashfree sandbox order:
    create order -> user pays (test card/UPI) -> signed ORDER_PAID webhook
    -> handler verifies + fetches order (must be PAID) -> Telegram invite
    -> /api/access returns granted + invite link.

Why a real order? The webhook handler re-fetches the order from Cashfree and
rejects it unless order_status == "PAID". Only an order the user actually paid
in the sandbox checkout satisfies that, so the invite cannot be forged.

Usage:
    python run_sandbox_e2e.py preflight            # check env vars (no network)
    python run_sandbox_e2e.py create               # create order via base server
    python run_sandbox_e2e.py webhook --order-id X # deliver signed webhook
    python run_sandbox_e2e.py check --order-id X   # poll /api/access
    python run_sandbox_e2e.py all                  # create -> wait -> webhook -> check

Env (loaded from .env if present):
    CASHFREE_CLIENT_ID, CASHFREE_CLIENT_SECRET, CASHFREE_WEBHOOK_SECRET,
    DEEPSTREAM_BOT_TOKEN, DEEPSTREAM_PRO_CHANNEL_ID
Options:
    --base-url   where the payment backend lives (default http://localhost:8080)
    --email      test customer email (default e2e+<ts>@example.com)

IMPORTANT: the server this runs against must have the same env vars set in
its own environment (the local Python server is a separate process - start it
with `set -a; source .env; set +a; python -m deepstream.server`, or set them
as Netlify environment variables for the deployed functions).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from deepstream import config

REQUIRED = [
    config.CASHFREE_CLIENT_ID_ENV,
    config.CASHFREE_CLIENT_SECRET_ENV,
    config.CASHFREE_WEBHOOK_SECRET_ENV,
    config.TELEGRAM_TOKEN_ENV,
    config.PRO_CHANNEL_ENV,
]

STATE_FILE = Path(__file__).resolve().parent / ".sandbox_e2e_state.json"


def load_dotenv(path: Optional[Path] = None) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (no overrides)."""
    path = path or Path(__file__).resolve().parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def cmd_preflight(args: argparse.Namespace) -> int:
    """Verify local env vars and the target server's payment config."""
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    mode = os.environ.get(config.CASHFREE_ENV_ENV, "sandbox")
    print("=== Sandbox E2E preflight ===")
    print(f"Cashfree mode : {mode}")
    for name in REQUIRED:
        print(f"  {'OK  ' if os.environ.get(name) else 'MISS'} {name}")
    if missing:
        print("\nMissing env vars. Copy .env.example to .env and fill them in.")
        return 1
    if mode != "sandbox":
        print(f"\nWARNING: CASHFREE_ENV is '{mode}' - this harness must run in sandbox!")
        return 1

    # The target server (local server or Netlify function) needs its OWN env
    # vars: CASHFREE_CLIENT_ID/SECRET (fetch_order verification), a matching
    # CASHFREE_WEBHOOK_SECRET, and the Telegram creds for invite minting.
    base = args.base_url.rstrip("/")
    print(f"\nChecking target server {base}/api/payments_config ...")
    try:
        status, cfg = _http_json("GET", f"{base}/api/payments_config")
    except Exception as exc:
        print(f"FAIL: cannot reach {base} - is the server running / deployed? ({exc})")
        return 1
    if status != 200 or not cfg.get("configured"):
        print("FAIL: target server reports configured:false - set CASHFREE_CLIENT_ID /")
        print("      CASHFREE_CLIENT_SECRET (and CASHFREE_WEBHOOK_SECRET, the Telegram")
        print("      vars) in the server's environment, then redeploy/restart.")
        return 1
    if cfg.get("mode") != "sandbox":
        print(f"FAIL: target server is in mode '{cfg.get('mode')}' - must be sandbox for this test.")
        return 1
    print(f"Server OK - configured:true, mode:sandbox, {cfg.get('amount')} {cfg.get('currency')}")
    print("\nPreflight OK - run `python run_sandbox_e2e.py create` next.")
    print("Note: if testing the local server, start it with the same env, e.g.")
    print("      set -a; source .env; set +a; python -m deepstream.server")
    return 0


def _http_json(method: str, url: str, payload: Optional[dict] = None,
               timeout: int = 20) -> tuple[int, dict]:
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _sign_webhook(raw_body: bytes, secret: str, timestamp: str) -> str:
    message = (timestamp + raw_body.decode("utf-8")).encode("utf-8")
    return base64.b64encode(
        hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
    ).decode("ascii")


def _save_state(order_id: str, email: str, base_url: str) -> None:
    STATE_FILE.write_text(json.dumps({
        "order_id": order_id, "email": email, "base_url": base_url,
    }), encoding="utf-8")


def _load_state() -> dict[str, str]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def cmd_create(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    email = args.email
    print(f"=== Creating sandbox order at {base} ===")
    try:
        status, body = _http_json("POST", f"{base}/api/create-order", {
            "customer_email": email,
            "customer_phone": args.phone,
        })
    except urllib.error.HTTPError as exc:
        print(f"FAIL: create-order returned {exc.code}: {exc.read().decode(errors='replace')}")
        return 1
    except urllib.error.URLError as exc:
        print(f"FAIL: cannot reach {base} - is the server running? ({exc.reason})")
        return 1
    if status != 200 or not body.get("payment_session_id"):
        print(f"FAIL: create-order returned {status}: {body}")
        return 1
    order_id = body["order_id"]
    _save_state(order_id, email, base)
    print(f"order_id           : {order_id}")
    print(f"payment_session_id : {body['payment_session_id']}")
    print(f"order_status       : {body.get('order_status')}")
    print()
    print("NEXT: complete the payment in the sandbox checkout using one of:")
    print("  - Test card: 4111 1111 1111 1111 | any future expiry | CVV 123 | OTP 111000")
    print("  - Test UPI : testsuccess@gocash")
    print("  (Open the site, click Subscribe, enter the email, and pay.)")
    print(f"\nThen run: python run_sandbox_e2e.py webhook --order-id {order_id}")
    print(f"Finally : python run_sandbox_e2e.py check   --order-id {order_id}")
    return 0


def cmd_webhook(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    secret = os.environ.get(config.CASHFREE_WEBHOOK_SECRET_ENV, "")
    if not secret:
        print("FAIL: CASHFREE_WEBHOOK_SECRET not set")
        return 1
    event = {
        "type": "ORDER_PAID",
        "event_time": datetime.now(timezone.utc).isoformat(),
        "data": {
            "order": {"order_id": args.order_id},
            "customer_details": {"customer_email": args.email},
        },
    }
    raw = json.dumps(event).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = _sign_webhook(raw, secret, timestamp)
    req = urllib.request.Request(
        f"{base}/webhooks/cashfree", data=raw, method="POST", headers={
            "Content-Type": "application/json",
            "x-webhook-signature": signature,
            "x-webhook-timestamp": timestamp,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {"error": raw[:500] or "empty response"}
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8", errors="replace") or ""
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"error": raw[:500] or f"HTTP {status}"}
    except urllib.error.URLError as exc:
        print(f"FAIL: cannot reach {base} - is the server running? ({exc.reason})")
        return 1
    print(f"Webhook delivered -> {status} {json.dumps(body)}")
    if status == 200 and body.get("summary"):
        print(f"Summary: {body['summary']}")
    return 0 if status == 200 else 1


def cmd_check(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    url = f"{base}/api/access?order_id={args.order_id}"
    deadline = time.time() + args.wait
    granted = False
    while time.time() < deadline:
        try:
            status, body = _http_json("GET", url)
        except Exception as exc:
            print(f"  poll failed: {exc}")
        else:
            state = body.get("status")
            print(f"  [{state}] {body.get('message', '')}")
            if state == "granted":
                print()
                print("=== GRANTED ===")
                print(f"invite_link : {body.get('invite_link')}")
                print(f"expires_at  : {body.get('expires_at')}")
                print("Flow verified: order -> webhook -> invite -> access")
                granted = True
                break
            if state == "revoked":
                print("Order is not paid — the webhook was rejected. Complete the payment first.")
                return 1
        time.sleep(2)
    if not granted:
        print(f"Timed out after {args.wait}s. Is the local server / deployed function running?")
        return 1
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    rc = cmd_create(args)
    if rc:
        return rc
    state = _load_state()
    args.order_id = args.order_id or state.get("order_id", "")
    if not args.order_id:
        print("FAIL: could not determine order_id; run `create` manually first")
        return 1
    print(f"\nPausing {args.pay_wait}s for you to complete the sandbox payment...")
    print("Use test card 4111 1111 1111 1111 (CVV 123, OTP 111000) or UPI testsuccess@gocash.")
    time.sleep(args.pay_wait)
    rc = cmd_webhook(args)
    if rc:
        return rc
    return cmd_check(args)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8080",
                        help="payment backend base URL")
    parser.add_argument("--email", default=None, help="test customer email")
    parser.add_argument("--phone", default="9999999999",
                        help="test customer phone (Cashfree requires it)")
    parser.add_argument("--order-id", default=None, help="order id for webhook/check")
    parser.add_argument("--wait", type=int, default=60, help="poll timeout seconds")
    parser.add_argument("--pay-wait", type=int, default=120,
                        help="seconds to wait for the user to pay in `all` mode")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in [("preflight", cmd_preflight), ("create", cmd_create),
                     ("webhook", cmd_webhook), ("check", cmd_check),
                     ("all", cmd_all)]:
        p = sub.add_parser(name)
        p.set_defaults(func=fn)

    args = parser.parse_args(argv)
    load_dotenv()
    if not args.email:
        args.email = f"e2e+{int(time.time())}@example.com"
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
