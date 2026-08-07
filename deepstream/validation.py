"""Input validation helpers shared by the Deepstream HTTP server.

Emails, order ids, and phone numbers are validated server-side — never
trust the client alone. The patterns mirror the Netlify Function side
(``netlify/functions/_shared/cashfree.mjs``) so both backends behave
identically.
"""

from __future__ import annotations

import re

# Emails/order ids are validated server-side (never trust the client alone).
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ORDER_ID_RE = re.compile(r"^ds_[0-9a-f]{16}$")

# Cashfree's Create Order API requires a valid 10-15 digit phone number.
# We normalize to digits-only and reject anything else before the request is
# ever sent to the provider (an empty/malformed phone is a common cause of
# Cashfree's generic "api Request Failed" rejection).
PHONE_DIGITS_RE = re.compile(r"^\d{10,15}$")


def normalize_phone(value: str) -> str:
    """Strip non-digit characters from a phone number ('' when empty)."""
    return re.sub(r"\D", "", value or "")


def valid_email(value: str) -> bool:
    """True for a non-empty email under 254 chars matching the EMAIL_RE."""
    return bool(value and len(value) <= 254 and EMAIL_RE.match(value))


def valid_order_id(value: str) -> bool:
    """True for an order id under 64 chars matching the ORDER_ID_RE."""
    return bool(value and len(value) <= 64 and ORDER_ID_RE.match(value))


def valid_phone_digits(value: str) -> bool:
    """True when ``value`` is a 10-15 digit string (already normalized)."""
    return bool(value and PHONE_DIGITS_RE.match(value))
