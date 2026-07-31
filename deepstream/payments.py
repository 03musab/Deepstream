"""Gumroad payment integration and Pro fulfillment for Deepstream.

Flow:
1. A visitor clicks "Subscribe" on the landing site. The buy button links to
   the Gumroad hosted checkout for the Pro $29/mo membership.
2. Gumroad sends webhook notifications to ``POST /webhooks/gumroad`` (this
   module reacts to them). Because Gumroad does not sign webhook payloads,
   ``sale`` events are verified against the Gumroad API before any access is
   granted.
3. When a sale/subscription becomes active, the bot mints a single-use invite
   link to the private Pro Telegram channel and we store it against the
   subscription.
4. The customer's success page polls ``GET /api/access?sale_id=...`` and
   receives the invite link once the webhook has been processed.

Access is granted when a verified sale exists for an active subscription and
revoked on refund / subscription end / cancellation (matching Gumroad's
subscription lifecycle).
"""

from __future__ import annotations

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

GUMROAD_API_BASE = "https://api.gumroad.com/v2"

# Statuses that keep full Pro access.
GRANT_STATUSES = {"active", "trialing"}
# Statuses that strip Pro access.
REVOKE_STATUSES = {"ended", "refunded", "cancelled", "failed"}

# How far into the future a minted Telegram invite link is valid (seconds).
INVITE_LINK_TTL_SECONDS = 30 * 24 * 3600  # 30 days


# ---------------------------------------------------------------------------
# Gumroad API (used to verify webhooks, since Gumroad does not sign them)
# ---------------------------------------------------------------------------

def gumroad_api_get(path: str, params: Optional[dict[str, str]] = None) -> dict[str, Any]:
    """GET ``path`` on the Gumroad API. Raises on network/HTTP errors."""
    token = os.environ.get(config.GUMROAD_ACCESS_TOKEN_ENV)
    if not token:
        raise RuntimeError(f"{config.GUMROAD_ACCESS_TOKEN_ENV} is not configured")
    query = {"access_token": token}
    query.update(params or {})
    url = f"{GUMROAD_API_BASE}/{path}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_sale(sale_id: str) -> dict[str, Any]:
    """Fetch a sale from the Gumroad API. Raises on network/HTTP errors."""
    data = gumroad_api_get(f"sales/{urllib.parse.quote(sale_id)}")
    if not data.get("success"):
        raise RuntimeError(f"Gumroad API rejected sale lookup: {data.get('message')}")
    return data.get("sale") or {}


def verify_sale(sale: dict[str, Any]) -> bool:
    """Return True if a Gumroad sale is a valid, paid, un-refunded Pro sale."""
    product_id = os.environ.get(config.GUMROAD_PRODUCT_ID_ENV)
    if product_id and sale.get("product_id") != product_id:
        logger.warning("Sale %s is for a different product", sale.get("id"))
        return False
    if not sale.get("paid"):
        logger.warning("Sale %s is not paid", sale.get("id"))
        return False
    if sale.get("refunded"):
        logger.warning("Sale %s has been refunded", sale.get("id"))
        return False
    if not sale.get("subscription_id"):
        logger.warning("Sale %s is not attached to a subscription", sale.get("id"))
        return False
    return True


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
            "<subscription_id>": {
              "subscription_id": "...",
              "customer_id": "...",
              "customer_email": "...",
              "status": "active",
              "invite_link": "https://t.me/...",
              "created_at": "...", "updated_at": "...", "occurred_at": "..."
            }
          },
          "sales": {
            "<sale_id>": {
              "sale_id": "...",
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
                return {"subscriptions": {}, "sales": {}, "processed_events": {}}
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.exception("Corrupt subscription store; starting empty")
                return {"subscriptions": {}, "sales": {}, "processed_events": {}}

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

    def access_for_sale(self, sale_id: str) -> dict[str, Any]:
        """Return the access state a success page should display."""
        data = self.load()
        sale = data["sales"].get(sale_id)
        if not sale:
            return {"status": "pending", "message": "Sale not yet seen."}

        sub = data["subscriptions"].get(sale.get("subscription_id", ""))
        if not sub:
            return {"status": "pending", "message": "Processing payment…"}
        if sub.get("status") in GRANT_STATUSES and sub.get("invite_link"):
            return {
                "status": "granted",
                "invite_link": sub["invite_link"],
                "expires_at": sub.get("invite_expires_at"),
            }
        if sub.get("status") in REVOKE_STATUSES:
            return {"status": "revoked", "message": "Subscription canceled or ended."}
        return {"status": "pending", "message": "Processing payment…"}

    def _record_sale(self, sale_id: str, *, subscription_id: str,
                     customer_email: Optional[str], status: str = "completed") -> None:
        data = self.load()
        data["sales"][sale_id] = {
            "sale_id": sale_id,
            "subscription_id": subscription_id,
            "customer_email": customer_email,
            "status": status,
        }
        self.save(data)

    def _ensure_access(self, subscription_id: str, *, customer_id: str,
                       customer_email: Optional[str]) -> Optional[str]:
        """Grant access for ``subscription_id``; mint the invite link once."""
        data = self.load()
        sub = data["subscriptions"].get(subscription_id)

        if sub and sub.get("invite_link") and sub.get("status") in GRANT_STATUSES:
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
            "status": "active",
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

    def _sync_subscription(self, subscription_id: str, *, status: str,
                           customer_email: Optional[str] = None) -> None:
        """Store subscription state and grant/revoke access per the status."""
        data = self.load()
        existing = data["subscriptions"].get(subscription_id, {})
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "subscription_id": subscription_id,
            "customer_id": existing.get("customer_id", ""),
            "customer_email": customer_email or existing.get("customer_email"),
            "status": status,
            "invite_link": existing.get("invite_link"),
            "invite_expires_at": existing.get("invite_expires_at"),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
            "occurred_at": existing.get("occurred_at"),
        }
        data["subscriptions"][subscription_id] = record
        self.save(data)

        if status in GRANT_STATUSES and record.get("invite_link"):
            return
        if status in REVOKE_STATUSES:
            self._revoke_access(subscription_id)
        else:
            self._ensure_access(
                subscription_id,
                customer_id=record["customer_id"],
                customer_email=record["customer_email"],
            )

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

# Gumroad resource names → our handlers.
RESOURCE_GRANT = {"sale", "subscription_restarted"}
RESOURCE_REVOKE = {"refund", "subscription_ended", "cancellation"}
RESOURCE_IGNORE = {"dispute", "dispute_won", "subscription_updated"}


def _parse_webhook_body(raw_body: bytes, content_type: str) -> dict[str, Any]:
    """Parse a Gumroad webhook body (form-encoded Ping payload or JSON)."""
    ctype = (content_type or "").lower()
    text = raw_body.decode("utf-8")
    if "json" in ctype:
        return json.loads(text)
    return {k: v[0] if isinstance(v, list) else v
            for k, v in urllib.parse.parse_qs(text).items()}


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes"}


def handle_webhook_event(event: dict[str, Any]) -> str:
    """Process a single Gumroad webhook event. Returns a human-readable summary."""
    store = SubscriptionStore()
    resource = event.get("resource_name", "")
    sale_id = event.get("sale_id") or event.get("id")
    subscription_id = event.get("subscription_id")
    customer_email = event.get("email") or event.get("user_email")
    occurred_at = event.get("sale_timestamp") or event.get("created_at") or ""

    if resource in RESOURCE_GRANT:
        if not sale_id:
            return f"ignored {resource} (no sale_id)"
        event_id = f"{resource}:{sale_id}"
        if store.is_processed(event_id):
            return f"duplicate {event_id}"

        sale = fetch_sale(sale_id)  # raises → 500 → Gumroad retries
        if not verify_sale(sale):
            store._mark_processed(event_id, occurred_at)
            return f"rejected {resource} (unverified)"

        sub_id = subscription_id or sale.get("subscription_id")
        store._record_sale(
            sale_id,
            subscription_id=sub_id or "",
            customer_email=customer_email or sale.get("email"),
        )
        if sub_id:
            store._sync_subscription(
                sub_id,
                status="active",
                customer_email=customer_email or sale.get("email"),
            )
        store._mark_processed(event_id, occurred_at)
        return f"processed {resource} {sale_id}"

    if resource in RESOURCE_REVOKE:
        if not subscription_id:
            return f"ignored {resource} (no subscription_id)"
        event_id = f"{resource}:{subscription_id}"
        if store.is_processed(event_id):
            return f"duplicate {event_id}"

        if resource == "cancellation":
            # A cancellation request keeps access until the period ends;
            # only mark it as cancelled once the subscription has ended.
            store._sync_subscription(subscription_id, status="cancelled",
                                     customer_email=customer_email)
        else:
            store._sync_subscription(subscription_id, status="ended",
                                     customer_email=customer_email)
        store._mark_processed(event_id, occurred_at)
        return f"processed {resource} {subscription_id}"

    # Ignore remaining resources but still mark them seen.
    if sale_id:
        event_id = f"{resource}:{sale_id}"
    elif subscription_id:
        event_id = f"{resource}:{subscription_id}"
    else:
        return f"ignored {resource}"
    if not store.is_processed(event_id):
        store._mark_processed(event_id, occurred_at)
    return f"ignored {resource}"


def handle_webhook_request(raw_body: bytes, content_type: str) -> tuple[int, dict[str, Any]]:
    """Process a Gumroad webhook request.

    Returns ``(http_status, json_body)``. Gumroad does not sign webhook payloads,
    so ``sale`` events are verified against the Gumroad API before granting access.
    Any non-2xx response makes Gumroad retry hourly for up to 3 hours.
    """
    try:
        event = _parse_webhook_body(raw_body, content_type)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Gumroad webhook body could not be parsed")
        return 400, {"error": "invalid body"}

    if not event:
        return 400, {"error": "empty body"}

    try:
        summary = handle_webhook_event(event)
    except Exception:
        logger.exception("Failed to process Gumroad webhook")
        return 500, {"error": "processing failed"}
    return 200, {"success": True, "summary": summary}
