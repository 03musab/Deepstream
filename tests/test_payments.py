"""Unit tests for the Deepstream payment / fulfillment flow (Cashfree)."""

import base64
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from deepstream import config
from deepstream.payments import (
    SubscriptionStore,
    create_cashfree_order,
    handle_webhook_event,
    handle_webhook_request,
    verify_webhook_signature,
)


def _sign(raw_body: bytes, secret: str = "test-webhook-secret",
          timestamp: str = "1722400000") -> dict:
    """Return the headers Cashfree would send for ``raw_body``."""
    message = (timestamp + raw_body.decode("utf-8")).encode()
    signature = base64.b64encode(
        hmac.new(secret.encode(), message, hashlib.sha256).digest()
    ).decode()
    return {"x-webhook-signature": signature, "x-webhook-timestamp": timestamp}


def _paid_event(order_id: str = "ds_abc123", **overrides) -> dict:
    event = {
        "type": "ORDER_PAID",
        "event_time": "2026-07-31T12:00:00+05:30",
        "data": {
            "order": {
                "order_id": order_id,
                "order_status": "PAID",
                "cf_order_id": "1234567890",
                "order_amount": 29.0,
                "order_currency": "USD",
            },
            "customer_details": {
                "customer_id": "cust_01",
                "customer_email": "pro@example.com",
                "customer_phone": "9999999999",
            },
        },
    }
    event.update(overrides)
    return event


class TestSubscriptionStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store_path = Path(self._tmp.name) / "subscriptions.json"
        self._orig_file = config.SUBSCRIPTIONS_FILE
        config.SUBSCRIPTIONS_FILE = self.store_path
        self.store = SubscriptionStore(self.store_path)
        self._env = os.environ.copy()
        os.environ[config.TELEGRAM_TOKEN_ENV] = "test-bot-token"
        os.environ[config.PRO_CHANNEL_ENV] = "-1001234567890"
        os.environ[config.CASHFREE_CLIENT_ID_ENV] = "cf-client-id"
        os.environ[config.CASHFREE_CLIENT_SECRET_ENV] = "cf-client-secret"
        os.environ[config.CASHFREE_WEBHOOK_SECRET_ENV] = "test-webhook-secret"
        os.environ[config.CASHFREE_ORDER_AMOUNT_ENV] = "29"
        os.environ[config.CASHFREE_ORDER_CURRENCY_ENV] = "USD"

    def tearDown(self):
        config.SUBSCRIPTIONS_FILE = self._orig_file
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_order")
    def test_grant_on_verified_paid_order(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "order_id": "ds_abc123",
            "cf_order_id": "1234567890",
            "order_status": "PAID",
            "order_amount": 29.0,
            "order_currency": "USD",
            "customer_details": {"customer_email": "pro@example.com"},
        }
        result = handle_webhook_event(_paid_event())
        self.assertIn("processed", result)
        mock_invite.assert_called_once()
        access = self.store.access_for_order("ds_abc123")
        self.assertEqual(access["status"], "granted")
        self.assertEqual(access["invite_link"], "https://t.me/+abc123")

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_order")
    def test_unpaid_order_is_rejected(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "order_id": "ds_abc123",
            "order_status": "ACTIVE",
            "order_amount": 29.0,
            "order_currency": "USD",
        }
        result = handle_webhook_event(_paid_event())
        self.assertIn("rejected", result)
        mock_invite.assert_not_called()
        self.assertEqual(self.store.access_for_order("ds_abc123")["status"], "pending")

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_order")
    def test_wrong_amount_is_rejected(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "order_id": "ds_abc123",
            "order_status": "PAID",
            "order_amount": 1.0,  # tampered amount
            "order_currency": "USD",
        }
        result = handle_webhook_event(_paid_event())
        self.assertIn("rejected", result)
        mock_invite.assert_not_called()

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_order")
    def test_duplicate_order_paid_is_idempotent(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "order_id": "ds_abc123",
            "order_status": "PAID",
            "order_amount": 29.0,
            "order_currency": "USD",
        }
        handle_webhook_event(_paid_event())
        handle_webhook_event(_paid_event())
        self.assertEqual(mock_invite.call_count, 1)

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_order")
    def test_revoke_on_refund(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "order_id": "ds_abc123",
            "order_status": "PAID",
            "order_amount": 29.0,
            "order_currency": "USD",
        }
        handle_webhook_event(_paid_event())

        refund = {
            "type": "REFUND_STATUS",
            "event_time": "2026-08-01T12:00:00+05:30",
            "data": {
                "order": {"order_id": "ds_abc123"},
                "refund": {"refund_status": "SUCCESS"},
            },
        }
        with mock.patch("deepstream.payments.revoke_channel_invite") as mock_revoke:
            result = handle_webhook_event(refund)
        mock_revoke.assert_called_once()
        self.assertIn("processed", result)

        data = self.store.load()
        order = data["orders"]["ds_abc123"]
        self.assertIsNone(order["invite_link"])
        self.assertEqual(order["status"], "refunded")

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_order")
    def test_revoke_when_order_id_only_under_refund(self, mock_fetch, mock_invite):
        """REFUND_STATUS events may nest order_id under data.refund."""
        mock_fetch.return_value = {
            "order_id": "ds_abc123",
            "order_status": "PAID",
            "order_amount": 29.0,
            "order_currency": "USD",
        }
        handle_webhook_event(_paid_event())

        refund = {
            "type": "REFUND_STATUS",
            "event_time": "2026-08-01T12:00:00+05:30",
            "data": {
                # No data.order — order reference lives on the refund object.
                "refund": {"order_id": "ds_abc123", "refund_status": "SUCCESS"},
            },
        }
        with mock.patch("deepstream.payments.revoke_channel_invite") as mock_revoke:
            result = handle_webhook_event(refund)
        mock_revoke.assert_called_once()
        self.assertIn("processed", result)
        self.assertIsNone(self.store.load()["orders"]["ds_abc123"]["invite_link"])

    @mock.patch("deepstream.payments.fetch_order")
    def test_order_failed_event_marks_failed(self, mock_fetch):
        failed = {
            "type": "ORDER_FAILED",
            "event_time": "2026-07-31T13:00:00+05:30",
            "data": {
                "order": {"order_id": "ds_abc123", "order_status": "FAILED"},
            },
        }
        result = handle_webhook_event(failed)
        self.assertIn("processed", result)
        access = self.store.access_for_order("ds_abc123")
        self.assertEqual(access["status"], "revoked")

    def test_access_pending_before_webhook(self):
        access = self.store.access_for_order("ds_unknown")
        self.assertEqual(access["status"], "pending")

    def test_no_telegram_credentials_logs_warning(self):
        os.environ.pop(config.TELEGRAM_TOKEN_ENV, None)
        os.environ.pop(config.PRO_CHANNEL_ENV, None)
        with mock.patch("deepstream.payments.fetch_order") as mock_fetch:
            mock_fetch.return_value = {
                "order_id": "ds_abc123",
                "order_status": "PAID",
                "order_amount": 29.0,
                "order_currency": "USD",
            }
            result = handle_webhook_event(_paid_event())
        self.assertIn("processed", result)
        access = self.store.access_for_order("ds_abc123")
        self.assertEqual(access["status"], "pending")


class TestSignatureVerification(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.copy()
        os.environ[config.CASHFREE_WEBHOOK_SECRET_ENV] = "test-webhook-secret"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_valid_signature_passes(self):
        body = json.dumps(_paid_event()).encode()
        headers = _sign(body)
        self.assertTrue(verify_webhook_signature(body, headers))

    def test_wrong_secret_fails(self):
        body = json.dumps(_paid_event()).encode()
        headers = _sign(body, secret="other-secret")
        self.assertFalse(verify_webhook_signature(body, headers))

    def test_tampered_body_fails(self):
        body = json.dumps(_paid_event()).encode()
        headers = _sign(body)
        tampered = body.replace(b"PAID", b"FAILED")
        self.assertFalse(verify_webhook_signature(tampered, headers))

    def test_missing_signature_fails(self):
        body = json.dumps(_paid_event()).encode()
        self.assertFalse(verify_webhook_signature(body, {}))


class TestWebhookRequest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_file = config.SUBSCRIPTIONS_FILE
        config.SUBSCRIPTIONS_FILE = Path(self._tmp.name) / "subscriptions.json"
        self._env = os.environ.copy()
        os.environ[config.CASHFREE_CLIENT_ID_ENV] = "cf-client-id"
        os.environ[config.CASHFREE_CLIENT_SECRET_ENV] = "cf-client-secret"
        os.environ[config.CASHFREE_WEBHOOK_SECRET_ENV] = "test-webhook-secret"
        os.environ[config.TELEGRAM_TOKEN_ENV] = "test-bot-token"
        os.environ[config.PRO_CHANNEL_ENV] = "-1001234567890"
        os.environ[config.CASHFREE_ORDER_AMOUNT_ENV] = "29"
        os.environ[config.CASHFREE_ORDER_CURRENCY_ENV] = "USD"

    def tearDown(self):
        config.SUBSCRIPTIONS_FILE = self._orig_file
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_order")
    def test_handle_request_signed_paid_order(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "order_id": "ds_abc123",
            "order_status": "PAID",
            "order_amount": 29.0,
            "order_currency": "USD",
        }
        body = json.dumps(_paid_event()).encode()
        status, resp = handle_webhook_request(body, _sign(body))
        self.assertEqual(status, 200)
        self.assertTrue(resp["success"])
        mock_invite.assert_called_once()

    @mock.patch("deepstream.payments.fetch_order")
    def test_handle_request_invalid_signature_returns_401(self, mock_fetch):
        body = json.dumps(_paid_event()).encode()
        headers = _sign(body, secret="wrong-secret")
        status, resp = handle_webhook_request(body, headers)
        self.assertEqual(status, 401)
        mock_fetch.assert_not_called()

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_order")
    def test_handle_request_order_lookup_failure_returns_500(self, mock_fetch, mock_invite):
        mock_fetch.side_effect = RuntimeError("API down")
        body = json.dumps(_paid_event()).encode()
        status, resp = handle_webhook_request(body, _sign(body))
        self.assertEqual(status, 500)

    def test_handle_request_invalid_body(self):
        status, resp = handle_webhook_request(b"not-json", _sign(b"not-json"))
        self.assertEqual(status, 400)


class TestCreateOrder(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.copy()
        os.environ[config.CASHFREE_CLIENT_ID_ENV] = "cf-client-id"
        os.environ[config.CASHFREE_CLIENT_SECRET_ENV] = "cf-client-secret"
        os.environ[config.CASHFREE_ENV_ENV] = "sandbox"
        os.environ[config.CASHFREE_ORDER_AMOUNT_ENV] = "29"
        os.environ[config.CASHFREE_ORDER_CURRENCY_ENV] = "USD"
        os.environ[config.CASHFREE_SITE_URL_ENV] = "https://deepstream.example"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_create_order_builds_payload_and_returns_session(self):
        from unittest import mock as m

        with m.patch("deepstream.payments._cashfree_request") as mock_request:
            mock_request.return_value = {
                "order_id": "ds_xyz",
                "payment_session_id": "session_123",
                "order_status": "ACTIVE",
            }
            result = create_cashfree_order("pro@example.com", "+919999999999")

        self.assertEqual(result["payment_session_id"], "session_123")
        self.assertTrue(result["order_id"].startswith("ds_"))
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(args[1], "/pg/orders")
        payload = kwargs["payload"] if "payload" in kwargs else args[2]
        self.assertEqual(payload["order_amount"], 29.0)
        self.assertEqual(payload["order_currency"], "USD")
        self.assertEqual(payload["customer_details"]["customer_email"], "pro@example.com")
        self.assertEqual(payload["order_meta"]["return_url"],
                         "https://deepstream.example/success.html")

    def test_create_order_raises_without_credentials(self):
        os.environ.pop(config.CASHFREE_CLIENT_ID_ENV, None)
        os.environ.pop(config.CASHFREE_CLIENT_SECRET_ENV, None)
        with self.assertRaises(RuntimeError):
            create_cashfree_order("pro@example.com")


if __name__ == "__main__":
    unittest.main()
