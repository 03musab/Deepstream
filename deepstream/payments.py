"""Cashfree payment integration and Pro fulfillment for Deepstream.

Flow:
1. A visitor clicks "Subscribe" on the landing site. The frontend posts their
   email/phone to ``POST /api/create-order``; this module creates a Cashfree
   order (``POST /pg/orders``) for one month of Pro access ($29 USD) and
   returns the ``payment_session_id`` used to render Cashfree's hosted/drop-in
   checkout (JS SDK v3).
2. The customer pays on Cashfree's hosted page. Cashfree redirects them back
   to ``success.html?order_id=...`` and sends webhook notifications to
   ``POST /webhooks/cashfree`` (this module reacts to them). Webhooks are
   signed with an HMAC-SHA256 signature (``x-webhook-signature`` header) over
   the raw payload plus the ``x-webhook-timestamp`` header, using the webhook
   secret — requests that fail verification are rejected.
3. When a ``ORDER_PAID`` event is verified, the bot mints a single-use invite
   link to the private Pro Telegram channel and we store it against the order.
4. The customer's success page polls ``GET /api/access?order_id=...`` and
   receives the invite link once the webhook has been processed.

Access is granted when a verified, paid order exists and revoked on refund /
failed payment (matching Cashfree's order lifecycle).

Billing model: Cashfree's auto-recurring e-mandate subscriptions are INR-only,
so the USD Pro tier is sold as a monthly order. Each successful payment grants
30 days of access via a fresh invite link; renewals are new orders from the
same customer.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from deepstream import config
from deepstream.logging_setup import setup_logging

logger = setup_logging()

CASHFREE_API_BASE_SANDBOX = "https://sandbox.cashfree.com"
CASHFREE_API_BASE_PRODUCTION = "https://api.cashfree.com"
DEFAULT_API_VERSION = "2023-08-01"

# Statuses that keep full Pro access.
GRANT_STATUSES = {"paid"}
# Statuses that strip Pro access.
REVOKE_STATUSES = {"failed", "cancelled", "refunded"}

# How far into the future a minted Telegram invite link is valid (seconds).
INVITE_LINK_TTL_SECONDS = 30 * 24 * 3600  # 30 days


class CashfreeError(RuntimeError):
    """A Cashfree API request was rejected (non-2xx) or otherwise failed.

    Carries the provider's ``status`` and ``code`` so callers can surface the
    real reason (e.g. the merchant sandbox account rejecting order creation)
    instead of a generic message.
    """

    def __init__(self, message: str, *, status: int = 0, code: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code


# ---------------------------------------------------------------------------
# Cashfree API (server-side only — never expose the client secret to the site)
# ---------------------------------------------------------------------------

def cashfree_base_url() -> str:
    mode = os.environ.get(config.CASHFREE_ENV_ENV, "sandbox").strip().lower()
    return CASHFREE_API_BASE_PRODUCTION if mode == "production" else CASHFREE_API_BASE_SANDBOX


def _cashfree_request(method: str, path: str,
                      payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Call the Cashfree PG API. Raises on network/HTTP errors."""
    client_id = os.environ.get(config.CASHFREE_CLIENT_ID_ENV)
    client_secret = os.environ.get(config.CASHFREE_CLIENT_SECRET_ENV)
    if not (client_id and client_secret):
        raise RuntimeError(
            f"{config.CASHFREE_CLIENT_ID_ENV} / {config.CASHFREE_CLIENT_SECRET_ENV} not configured"
        )
    headers = {
        "x-api-version": os.environ.get(config.CASHFREE_API_VERSION_ENV, DEFAULT_API_VERSION),
        "x-client-id": client_id,
        "x-client-secret": client_secret,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{cashfree_base_url()}{path}", data=body, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Cashfree returns the real reason in the JSON body (e.g.
        # {"message": "api Request Failed", "code": "request_failed"}).
        # Preserve it instead of collapsing to a generic failure.
        detail, code = "", ""
        try:
            err_body = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str(err_body.get("message") or "")
            code = str(err_body.get("code") or "")
        except (ValueError, TypeError):
            pass
        raise CashfreeError(
            detail or f"Cashfree API error (HTTP {exc.code})",
            status=exc.code, code=code,
        ) from exc


def create_cashfree_order(customer_email: str, customer_phone: str = "") -> dict[str, Any]:
    """Create a Cashfree order for one month of Pro access.

    Returns ``{order_id, payment_session_id, order_status}``. The
    ``payment_session_id`` is what the frontend hands to the Cashfree JS SDK.
    """
    order_id = "ds_" + uuid.uuid4().hex[:16]
    amount = float(os.environ.get(config.CASHFREE_ORDER_AMOUNT_ENV, "29"))
    currency = os.environ.get(config.CASHFREE_ORDER_CURRENCY_ENV, "USD")
    site_url = os.environ.get(config.CASHFREE_SITE_URL_ENV, "").strip().rstrip("/")

    payload: dict[str, Any] = {
        "order_id": order_id,
        "order_amount": amount,
        "order_currency": currency,
        "order_note": "Deepstream Pro — 30 day access",
        "customer_details": {
            "customer_id": "cust_" + uuid.uuid4().hex[:12],
            "customer_email": customer_email,
            "customer_phone": customer_phone,
        },
    }
    if site_url:
        payload["order_meta"] = {"return_url": f"{site_url}/success.html"}

    data = _cashfree_request("POST", "/pg/orders", payload)
    return {
        "order_id": order_id,
        "payment_session_id": data.get("payment_session_id") or "",
        "order_status": data.get("order_status") or "",
    }


def fetch_order(order_id: str) -> dict[str, Any]:
    """Fetch an order from the Cashfree API. Raises on network/HTTP errors."""
    return _cashfree_request("GET", f"/pg/orders/{urllib.parse.quote(order_id)}")


def payments_config() -> dict[str, Any]:
    """Public-safe config the landing page needs to render the Cashfree SDK."""
    return {
        "configured": bool(os.environ.get(config.CASHFREE_CLIENT_ID_ENV)),
        "mode": os.environ.get(config.CASHFREE_ENV_ENV, "sandbox").strip().lower(),
        "amount": float(os.environ.get(config.CASHFREE_ORDER_AMOUNT_ENV, "29")),
        "currency": os.environ.get(config.CASHFREE_ORDER_CURRENCY_ENV, "USD"),
    }


# ---------------------------------------------------------------------------
# Webhook signature verification
# ---------------------------------------------------------------------------

def verify_webhook_signature(raw_body: bytes, headers: dict[str, str]) -> bool:
    """Verify the Cashfree webhook ``x-webhook-signature`` header.

    Cashfree signs the payload with HMAC-SHA256 using the webhook secret
    configured in the dashboard. The signed message is the raw request body
    (optionally prefixed with the ``x-webhook-timestamp`` header depending on
    API version). We accept either form and compare in constant time.
    """
    secret = os.environ.get(config.CASHFREE_WEBHOOK_SECRET_ENV, "")
    # HTTP header names are case-insensitive; clients (urllib, http servers,
    # proxies) may deliver any casing, so normalize before lookup.
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    signature = (headers.get("x-webhook-signature") or "").strip()
    if not (secret and signature):
        logger.warning("Webhook secret or signature header missing")
        return False

    body = raw_body.decode("utf-8", errors="replace")
    timestamp = (headers.get("x-webhook-timestamp") or "").strip()
    # Cashfree has shipped both body-only and timestamp+body signature schemes
    # (some versions insert a separator). Accept the documented variants.
    candidates = [body]
    if timestamp:
        candidates += [timestamp + body, timestamp + "." + body]

    for message in candidates:
        expected = base64.b64encode(
            hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
        ).decode("ascii")
        if hmac.compare_digest(expected, signature):
            return True
    return False


# ---------------------------------------------------------------------------
# Telegram invite link helpers (bot must be admin of the Pro channel)
# ---------------------------------------------------------------------------

def _telegram_post(bot_token: str, method: str, data: dict[str, Any]) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def create_channel_invite(bot_token: str, chat_id: str) -> str:
    """Mint a single-use invite link to ``chat_id``. Returns the link."""
    payload = _telegram_post(bot_token, "createChatInviteLink", {
        "chat_id": chat_id,
        "member_limit": 1,
        "expire_date": int(time.time()) + INVITE_LINK_TTL_SECONDS,
    })
    if not payload.get("ok"):
        raise RuntimeError(f"createChatInviteLink failed: {payload.get('description')}")
    return payload["result"]["invite_link"]


def revoke_channel_invite(bot_token: str, chat_id: str, invite_link: str) -> None:
    """Revoke a previously minted invite link so it can no longer be used."""
    payload = _telegram_post(bot_token, "revokeChatInviteLink", {
        "chat_id": chat_id,
        "invite_link": invite_link,
    })
    if not payload.get("ok"):
        raise RuntimeError(f"revokeChatInviteLink failed: {payload.get('description')}")


# ---------------------------------------------------------------------------
# Subscription store (lean cache of access decisions, keyed by order_id)
# ---------------------------------------------------------------------------

class SubscriptionStore:
    """Persist order state so the success page can grant access.

    Shape (data/subscriptions.json)::

        {
          "orders": {
            "<order_id>": {
              "order_id": "...",
              "cf_order_id": "...",
              "customer_id": "...",
              "customer_email": "...",
              "status": "paid" | "failed" | "cancelled" | "refunded",
              "amount": 29.0,
              "currency": "USD",
              "invite_link": "https://t.me/...",
              "invite_expires_at": "...",
              "created_at": "...", "updated_at": "...", "occurred_at": "..."
            }
          },
          "processed_events": {"<event_id>": "<occurred_at>"}
        }
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = path or config.SUBSCRIPTIONS_FILE
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return {"orders": {}, "processed_events": {}}
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.exception("Corrupt subscription store; starting empty")
                return {"orders": {}, "processed_events": {}}

    def save(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self.path)

    def is_processed(self, event_id: str) -> bool:
        return event_id in self.load().get("processed_events", {})

    def _mark_processed(self, event_id: str, occurred_at: str) -> None:
        data = self.load()
        data["processed_events"][event_id] = occurred_at
        self.save(data)

    def access_for_order(self, order_id: str) -> dict[str, Any]:
        """Return the access state a success page should display."""
        data = self.load()
        order = data["orders"].get(order_id)
        if not order:
            return {"status": "pending", "message": "Order not yet seen."}

        if order.get("status") in GRANT_STATUSES and order.get("invite_link"):
            return {
                "status": "granted",
                "invite_link": order["invite_link"],
                "expires_at": order.get("invite_expires_at"),
            }
        if order.get("status") in REVOKE_STATUSES:
            return {"status": "revoked", "message": "Payment failed or was refunded."}
        return {"status": "pending", "message": "Processing payment…"}

    def _record_order(self, order_id: str, *, customer_email: Optional[str],
                      status: str = "pending", cf_order_id: str = "",
                      amount: Optional[float] = None, currency: Optional[str] = None,
                      occurred_at: str = "") -> None:
        data = self.load()
        now = datetime.now(timezone.utc).isoformat()
        existing = data["orders"].get(order_id, {})
        data["orders"][order_id] = {
            "order_id": order_id,
            "cf_order_id": existing.get("cf_order_id") or cf_order_id,
            "customer_id": existing.get("customer_id", ""),
            "customer_email": customer_email or existing.get("customer_email"),
            "status": status,
            "amount": amount if amount is not None else existing.get("amount"),
            "currency": currency or existing.get("currency"),
            "invite_link": existing.get("invite_link"),
            "invite_expires_at": existing.get("invite_expires_at"),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
            "occurred_at": occurred_at or existing.get("occurred_at"),
        }
        self.save(data)

    def _grant(self, order_id: str, *, cf_order_id: str = "",
               customer_email: Optional[str] = None,
               amount: Optional[float] = None, currency: Optional[str] = None,
               occurred_at: str = "") -> Optional[str]:
        """Mark an order paid and mint the invite link once."""
        data = self.load()
        existing = data["orders"].get(order_id, {})
        if existing.get("status") in GRANT_STATUSES and existing.get("invite_link"):
            return existing["invite_link"]

        token = os.environ.get(config.TELEGRAM_TOKEN_ENV)
        pro_channel = os.environ.get(config.PRO_CHANNEL_ENV)
        if not (token and pro_channel):
            logger.warning(
                "Pro channel not configured (set %s and %s) — cannot mint invite link",
                config.TELEGRAM_TOKEN_ENV, config.PRO_CHANNEL_ENV,
            )
            self._record_order(order_id, customer_email=customer_email, status="paid",
                               cf_order_id=cf_order_id, amount=amount, currency=currency,
                               occurred_at=occurred_at)
            return None

        now = datetime.now(timezone.utc).isoformat()
        invite_link = create_channel_invite(token, pro_channel)
        data["orders"][order_id] = {
            "order_id": order_id,
            "cf_order_id": cf_order_id or existing.get("cf_order_id", ""),
            "customer_id": existing.get("customer_id", ""),
            "customer_email": customer_email or existing.get("customer_email"),
            "status": "paid",
            "amount": amount if amount is not None else existing.get("amount"),
            "currency": currency or existing.get("currency"),
            "invite_link": invite_link,
            "invite_expires_at": datetime.fromtimestamp(
                time.time() + INVITE_LINK_TTL_SECONDS, tz=timezone.utc
            ).isoformat(),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
            "occurred_at": occurred_at or existing.get("occurred_at"),
        }
        self.save(data)
        logger.info("Granted Pro access for order %s", order_id)
        return invite_link

    def _mark_failed(self, order_id: str, *, customer_email: Optional[str] = None,
                     occurred_at: str = "") -> None:
        self._record_order(order_id, customer_email=customer_email, status="failed",
                           occurred_at=occurred_at)

    def _revoke(self, order_id: str, *, occurred_at: str = "") -> None:
        data = self.load()
        order = data["orders"].get(order_id)
        if not order:
            return
        invite_link = order.get("invite_link")
        token = os.environ.get(config.TELEGRAM_TOKEN_ENV)
        pro_channel = os.environ.get(config.PRO_CHANNEL_ENV)
        if invite_link and token and pro_channel:
            try:
                revoke_channel_invite(token, pro_channel, invite_link)
            except Exception:
                logger.exception("Failed to revoke invite link for %s", order_id)
        order["invite_link"] = None
        order["invite_expires_at"] = None
        order["status"] = "refunded"
        order["updated_at"] = datetime.now(timezone.utc).isoformat()
        order["occurred_at"] = occurred_at or order.get("occurred_at")
        data["orders"][order_id] = order
        self.save(data)
        logger.info("Revoked Pro access for order %s", order_id)


# ---------------------------------------------------------------------------
# Webhook dispatch
# ---------------------------------------------------------------------------

# Cashfree event names → how we treat them.
# Include common legacy/alias names defensively so grants/revocations are not
# silently dropped if Cashfree delivers a differently-named variant.
GRANT_TYPES = {"ORDER_PAID", "PAYMENT_SUCCESS_WEBHOOK"}
REVOKE_TYPES = {
    "REFUND_STATUS", "REFUND_STATUS_CHANGE",
    "REFUND_STATUS_WEBHOOK", "REFUND_SUCCESS",
}
FAIL_TYPES = {
    "ORDER_FAILED", "ORDER_CANCELLED", "PAYMENT_FAILED",
    "PAYMENT_FAILED_WEBHOOK",
}


def _order_id_from_event(event: dict[str, Any]) -> str:
    data = event.get("data") or {}
    order = data.get("order") or {}
    refund = data.get("refund") or {}
    return str(
        order.get("order_id")
        or data.get("order_id")
        or refund.get("order_id")
        or ""
    )


def handle_webhook_event(event: dict[str, Any]) -> str:
    """Process a single Cashfree webhook event. Returns a human-readable summary."""
    store = SubscriptionStore()
    etype = event.get("type", "")
    data = event.get("data") or {}
    order = data.get("order") or {}
    customer = data.get("customer_details") or {}
    order_id = _order_id_from_event(event)
    occurred_at = event.get("event_time") or event.get("created_at") or ""
    customer_email = customer.get("customer_email")

    if not order_id:
        return f"ignored {etype} (no order_id)"

    event_id = f"{etype}:{order_id}"
    if store.is_processed(event_id):
        return f"duplicate {event_id}"

    if etype in GRANT_TYPES:
        # Verify against the Cashfree API before granting access.
        fetched = fetch_order(order_id)  # raises → 500 → Cashfree retries
        if fetched.get("order_status") != "PAID":
            store._mark_processed(event_id, occurred_at)
            return f"rejected {etype} (order not PAID)"
        expected_amount = float(os.environ.get(config.CASHFREE_ORDER_AMOUNT_ENV, "29"))
        if float(fetched.get("order_amount") or 0) != expected_amount:
            store._mark_processed(event_id, occurred_at)
            return f"rejected {etype} (amount mismatch)"
        if fetched.get("order_currency") != os.environ.get(
                config.CASHFREE_ORDER_CURRENCY_ENV, "USD"):
            store._mark_processed(event_id, occurred_at)
            return f"rejected {etype} (currency mismatch)"

        store._grant(
            order_id,
            cf_order_id=str(fetched.get("cf_order_id") or order.get("cf_order_id") or ""),
            customer_email=customer_email or (fetched.get("customer_details") or {}).get("customer_email"),
            amount=fetched.get("order_amount"),
            currency=fetched.get("order_currency"),
            occurred_at=occurred_at,
        )
        store._mark_processed(event_id, occurred_at)
        return f"processed {etype} {order_id}"

    if etype in REVOKE_TYPES:
        refund = data.get("refund") or {}
        if refund.get("refund_status") not in ("SUCCESS", "PENDING", None):
            store._mark_processed(event_id, occurred_at)
            return f"ignored {etype} (refund not successful)"
        store._revoke(order_id, occurred_at=occurred_at)
        store._mark_processed(event_id, occurred_at)
        return f"processed {etype} {order_id}"

    if etype in FAIL_TYPES:
        store._mark_failed(order_id, customer_email=customer_email, occurred_at=occurred_at)
        store._mark_processed(event_id, occurred_at)
        return f"processed {etype} {order_id}"

    # Ignore remaining event types but still mark them seen.
    store._mark_processed(event_id, occurred_at)
    return f"ignored {etype}"


def handle_webhook_request(raw_body: bytes, headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
    """Process a Cashfree webhook request.

    Returns ``(http_status, json_body)``. Requests with an invalid
    ``x-webhook-signature`` are rejected with 401. Any other non-2xx response
    makes Cashfree retry.
    """
    if not verify_webhook_signature(raw_body, headers):
        logger.warning("Cashfree webhook signature verification failed")
        return 401, {"error": "invalid signature"}

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Cashfree webhook body could not be parsed")
        return 400, {"error": "invalid body"}

    if not event:
        return 400, {"error": "empty body"}

    try:
        summary = handle_webhook_event(event)
    except Exception:
        logger.exception("Failed to process Cashfree webhook")
        return 500, {"error": "processing failed"}
    return 200, {"success": True, "summary": summary}
