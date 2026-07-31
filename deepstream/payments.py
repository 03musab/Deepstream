"""Paddle payment integration and Pro fulfillment for Deepstream.

Flow:
1. A visitor clicks "Subscribe" on the landing site. Paddle.js opens a
   hosted overlay checkout for the Pro $29/mo price.
2. Paddle sends webhook events to ``POST /webhooks/paddle`` (this module
   verifies the HMAC signature and reacts to them).
3. When a subscription becomes active, the bot mints a single-use invite
   link to the private Pro Telegram channel and we store it against the
   transaction / subscription.
4. The customer's success page polls ``GET /api/access?transaction_id=...``
   and receives the invite link once the webhook has been processed.

Access is granted when the subscription is ``active``/``trialing``/``past_due``
and revoked when it is ``canceled``/``paused`` (matching Paddle's recommended
access matrix for lean-cache provisioning).
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from deepstream import config
from deepstream.logging_setup import setup_logging

logger = setup_logging()

# ---------------------------------------------------------------------------
# Paddle webhook signature verification
# ---------------------------------------------------------------------------

# Statuses that keep full Pro access (Paddle access matrix).
GRANT_STATUSES = {"active", "trialing", "past_due"}
# Statuses that strip Pro access.
REVOKE_STATUSES = {"canceled", "paused"}

# Replay tolerance: Paddle signs with a unix timestamp. We accept events up to
# this many seconds old so legitimate retries (minutes later) are not dropped.
SIGNATURE_TOLERANCE_SECONDS = 300

# How far into the future a minted Telegram invite link is valid (seconds).
INVITE_LINK_TTL_SECONDS = 30 * 24 * 3600  # 30 days


def verify_paddle_signature(secret_key: str, signature_header: str, raw_body: bytes) -> bool:
    """Return True if ``signature_header`` matches the HMAC-SHA256 of ``raw_body``.

    Paddle signs webhooks as ``ts=<unix>;h1=<hex hmac sha256>`` where the signed
    payload is ``f"{ts}:{raw_body}"``. See
    https://developer.paddle.com/webhooks/about/signature-verification
    """
    parts: dict[str, str] = {}
    for piece in signature_header.split(";"):
        if "=" in piece:
            key, _, value = piece.partition("=")
            parts[key] = value

    ts_raw, h1 = parts.get("ts"), parts.get("h1")
    if not ts_raw or not h1:
        logger.warning("Paddle signature header missing ts/h1 fields")
        return False

    try:
        ts = int(ts_raw)
    except ValueError:
        logger.warning("Paddle signature timestamp is not an integer")
        return False

    if abs(time.time() - ts) > SIGNATURE_TOLERANCE_SECONDS:
        logger.warning(
            "Paddle signature timestamp %s outside tolerance", ts
        )
        return False

    signed_payload = f"{ts}:{raw_body.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(secret_key.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, h1)


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
# Subscription store (lean cache of access decisions)
# ---------------------------------------------------------------------------

class SubscriptionStore:
    """Persist subscription state so the success page can grant access.

    Shape (data/subscriptions.json)::

        {
          "subscriptions": {
            "<sub_id>": {
              "subscription_id": "...",
              "customer_id": "...",
              "customer_email": "...",
              "status": "active",
              "invite_link": "https://t.me/...",
              "created_at": "...", "updated_at": "...", "occurred_at": "..."
            }
          },
          "transactions": {
            "<txn_id>": {
              "transaction_id": "...",
              "subscription_id": "...",
              "customer_email": "...",
              "status": "completed"
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
                return {"subscriptions": {}, "transactions": {}, "processed_events": {}}
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.exception("Corrupt subscription store; starting empty")
                return {"subscriptions": {}, "transactions": {}, "processed_events": {}}

    def save(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self.path)

    def is_processed(self, event_id: str) -> bool:
        return event_id in self.load().get("processed_events", {})

    def _mark_processed(self, event_id: str, event: dict[str, Any]) -> None:
        data = self.load()
        data["processed_events"][event_id] = event.get("occurred_at", "")
        self.save(data)

    def access_for_transaction(self, transaction_id: str) -> dict[str, Any]:
        """Return the access state a success page should display."""
        data = self.load()
        txn = data["transactions"].get(transaction_id)
        if not txn:
            return {"status": "pending", "message": "Transaction not yet seen."}

        sub = data["subscriptions"].get(txn.get("subscription_id", ""))
        if not sub:
            return {"status": "pending", "message": "Processing payment…"}
        if sub.get("status") in GRANT_STATUSES and sub.get("invite_link"):
            return {
                "status": "granted",
                "invite_link": sub["invite_link"],
                "expires_at": sub.get("invite_expires_at"),
            }
        if sub.get("status") in REVOKE_STATUSES:
            return {"status": "revoked", "message": "Subscription canceled."}
        return {"status": "pending", "message": "Processing payment…"}

    def _record_transaction(self, txn: dict[str, Any]) -> None:
        data = self.load()
        data["transactions"][txn["transaction_id"]] = txn
        self.save(data)

    def _ensure_access(self, subscription_id: str, *, customer_id: str, customer_email: Optional[str]) -> Optional[str]:
        """Grant access for ``subscription_id``; mint the invite link once."""
        data = self.load()
        sub = data["subscriptions"].get(subscription_id)

        if sub and sub.get("invite_link"):
            return sub["invite_link"]

        token = os.environ.get(config.TELEGRAM_TOKEN_ENV)
        pro_channel = os.environ.get(config.PRO_CHANNEL_ENV)
        if not (token and pro_channel):
            logger.warning(
                "Pro channel not configured (set %s and %s) — cannot mint invite link",
                config.TELEGRAM_TOKEN_ENV, config.PRO_CHANNEL_ENV,
            )
            return None

        now = datetime.now(timezone.utc).isoformat()
        invite_link = create_channel_invite(token, pro_channel)
        existing = sub or {}
        sub = {
            "subscription_id": subscription_id,
            "customer_id": existing.get("customer_id") or customer_id,
            "customer_email": existing.get("customer_email") or customer_email,
            "status": existing.get("status") or "active",
            "invite_link": invite_link,
            "invite_expires_at": datetime.fromtimestamp(
                time.time() + INVITE_LINK_TTL_SECONDS, tz=timezone.utc
            ).isoformat(),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
            "occurred_at": existing.get("occurred_at"),
        }
        data["subscriptions"][subscription_id] = sub
        self.save(data)
        logger.info("Granted Pro access for subscription %s", subscription_id)
        return invite_link

    def _sync_subscription(self, event: dict[str, Any], sub: dict[str, Any]) -> None:
        """Store subscription state and grant/revoke access per Paddle's matrix."""
        data = self.load()
        sub_id = sub.get("id") or sub.get("subscription_id")
        if not sub_id:
            logger.warning("Subscription event without an id: %s", event.get("event_type"))
            return

        status = sub.get("status")
        existing = data["subscriptions"].get(sub_id, {})
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "subscription_id": sub_id,
            "customer_id": sub.get("customer_id") or existing.get("customer_id"),
            "customer_email": sub.get("customer_email") or existing.get("customer_email"),
            "status": status,
            "invite_link": existing.get("invite_link"),
            "invite_expires_at": existing.get("invite_expires_at"),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
            "occurred_at": event.get("occurred_at") or existing.get("occurred_at"),
        }
        data["subscriptions"][sub_id] = record
        self.save(data)

        if status in GRANT_STATUSES:
            self._ensure_access(
                sub_id,
                customer_id=record["customer_id"] or "",
                customer_email=record["customer_email"],
            )
        elif status in REVOKE_STATUSES:
            self._revoke_access(sub_id)

    def _revoke_access(self, subscription_id: str) -> None:
        data = self.load()
        sub = data["subscriptions"].get(subscription_id)
        if not sub:
            return
        invite_link = sub.get("invite_link")
        token = os.environ.get(config.TELEGRAM_TOKEN_ENV)
        pro_channel = os.environ.get(config.PRO_CHANNEL_ENV)
        if invite_link and token and pro_channel:
            try:
                revoke_channel_invite(token, pro_channel, invite_link)
            except Exception:
                logger.exception("Failed to revoke invite link for %s", subscription_id)
        sub["invite_link"] = None
        sub["invite_expires_at"] = None
        sub["updated_at"] = datetime.now(timezone.utc).isoformat()
        data["subscriptions"][subscription_id] = sub
        self.save(data)
        logger.info("Revoked Pro access for subscription %s", subscription_id)


# ---------------------------------------------------------------------------
# Webhook dispatch
# ---------------------------------------------------------------------------

def _extract_customer_email(sub: dict[str, Any]) -> Optional[str]:
    """Best-effort email extraction from a Paddle entity payload."""
    if sub.get("customer_email"):
        return sub["customer_email"]
    billing = sub.get("billing_details")
    if isinstance(billing, dict) and billing.get("email_address"):
        return billing["email_address"]
    customer = sub.get("customer")
    if isinstance(customer, dict) and customer.get("email"):
        return customer["email"]
    return None


def handle_webhook_event(event: dict[str, Any]) -> str:
    """Process a single Paddle webhook event. Returns a human-readable summary."""
    store = SubscriptionStore()
    event_id = event.get("event_id", "")
    if store.is_processed(event_id):
        return f"duplicate {event_id}"

    event_type = event.get("event_type", "")
    data = event.get("data", {})

    if event_type == "transaction.completed":
        txn_id = data.get("id")
        sub_id = data.get("subscription_id")
        if txn_id:
            store._record_transaction({
                "transaction_id": txn_id,
                "subscription_id": sub_id,
                "customer_email": _extract_customer_email(data),
                "status": data.get("status", "completed"),
            })
            if sub_id:
                # The initial payment is complete — grant straight away so the
                # success page resolves quickly even before subscription events land.
                store._ensure_access(
                    sub_id,
                    customer_id=data.get("customer_id", ""),
                    customer_email=_extract_customer_email(data),
                )
        store._mark_processed(event_id, event)
        return f"processed {event_type}"

    if event_type in {"subscription.created", "subscription.activated", "subscription.updated"}:
        sub = dict(data)
        sub.setdefault("customer_email", _extract_customer_email(data))
        store._sync_subscription(event, sub)
        store._mark_processed(event_id, event)
        return f"processed {event_type} (status={data.get('status')})"

    if event_type in {"subscription.canceled", "subscription.paused", "subscription.past_due"}:
        sub = dict(data)
        sub.setdefault("customer_email", _extract_customer_email(data))
        store._sync_subscription(event, sub)
        store._mark_processed(event_id, event)
        return f"processed {event_type} (status={data.get('status')})"

    # Ignore other events (customer.*, product.*, …) but still mark them seen.
    store._mark_processed(event_id, event)
    return f"ignored {event_type}"


def handle_webhook_request(raw_body: bytes, signature_header: str) -> tuple[int, dict[str, Any]]:
    """Verify a webhook request and process it.

    Returns ``(http_status, json_body)``. Mirrors Paddle's "ack then process"
    guidance: processing is synchronous here because Telegram calls are fast,
    but signature failure is rejected before any side effects.
    """
    secret = os.environ.get(config.PADDLE_WEBHOOK_SECRET_ENV)
    if not secret:
        logger.warning("Paddle webhook secret not configured (%s)", config.PADDLE_WEBHOOK_SECRET_ENV)
        return 503, {"error": "server not configured"}

    if not verify_paddle_signature(secret, signature_header, raw_body):
        logger.warning("Rejected webhook with invalid Paddle signature")
        return 401, {"error": "invalid signature"}

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        logger.warning("Webhook body is not valid JSON")
        return 400, {"error": "invalid json"}

    try:
        summary = handle_webhook_event(event)
    except Exception:
        logger.exception("Failed to process Paddle webhook")
        return 500, {"error": "processing failed"}
    return 200, {"success": True, "summary": summary}
