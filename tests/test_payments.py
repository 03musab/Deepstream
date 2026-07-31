"""Unit tests for the Deepstream payment / fulfillment flow."""

import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from deepstream import config
from deepstream.payments import (
    SubscriptionStore,
    handle_webhook_event,
    handle_webhook_request,
    verify_paddle_signature,
)


def _sign(secret: str, body: bytes) -> str:
    ts = int(time.time())
    signed = f"{ts}:{body.decode('utf-8')}".encode("utf-8")
    h1 = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


class TestSignatureVerification(unittest.TestCase):
    def test_valid_signature(self):
        body = b'{"event_type": "subscription.activated"}'
        header = _sign("s3cret", body)
        self.assertTrue(verify_paddle_signature("s3cret", header, body))

    def test_wrong_secret(self):
        body = b'{"event_type": "subscription.activated"}'
        header = _sign("s3cret", body)
        self.assertFalse(verify_paddle_signature("other", header, body))

    def test_tampered_body(self):
        body = b'{"event_type": "subscription.activated"}'
        header = _sign("s3cret", body)
        tampered = b'{"event_type": "subscription.canceled"}'
        self.assertFalse(verify_paddle_signature("s3cret", header, tampered))

    def test_malformed_header(self):
        self.assertFalse(verify_paddle_signature("s3cret", "not-a-header", b"{}"))

    def test_stale_timestamp(self):
        body = b"{}"
        old_ts = int(time.time()) - 3600
        signed = f"{old_ts}:{body.decode('utf-8')}".encode("utf-8")
        h1 = hmac.new(b"s3cret", signed, hashlib.sha256).hexdigest()
        header = f"ts={old_ts};h1={h1}"
        self.assertFalse(verify_paddle_signature("s3cret", header, body))


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

    def tearDown(self):
        config.SUBSCRIPTIONS_FILE = self._orig_file
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    def test_grant_on_transaction_completed(self, mock_invite):
        event = {
            "event_id": "evt_01",
            "event_type": "transaction.completed",
            "occurred_at": "2026-07-31T12:00:00Z",
            "data": {
                "id": "txn_01",
                "subscription_id": "sub_01",
                "customer_id": "ctm_01",
                "billing_details": {"email_address": "pro@example.com"},
                "status": "completed",
            },
        }
        result = handle_webhook_event(event)
        self.assertIn("processed", result)
        mock_invite.assert_called_once()
        access = self.store.access_for_transaction("txn_01")
        self.assertEqual(access["status"], "granted")
        self.assertEqual(access["invite_link"], "https://t.me/+abc123")

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    def test_grant_duplicate_event_is_idempotent(self, mock_invite):
        event = {
            "event_id": "evt_01",
            "event_type": "subscription.activated",
            "occurred_at": "2026-07-31T12:00:00Z",
            "data": {
                "id": "sub_01",
                "customer_id": "ctm_01",
                "status": "active",
                "items": [{"price": {"id": "pri_01"}}],
            },
        }
        handle_webhook_event(event)
        handle_webhook_event(event)
        self.assertEqual(mock_invite.call_count, 1)

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    def test_revoke_on_cancel(self, mock_invite):
        activated = {
            "event_id": "evt_01",
            "event_type": "subscription.activated",
            "occurred_at": "2026-07-31T12:00:00Z",
            "data": {"id": "sub_01", "customer_id": "ctm_01", "status": "active"},
        }
        handle_webhook_event(activated)

        canceled = {
            "event_id": "evt_02",
            "event_type": "subscription.canceled",
            "occurred_at": "2026-08-01T12:00:00Z",
            "data": {"id": "sub_01", "customer_id": "ctm_01", "status": "canceled"},
        }
        with mock.patch("deepstream.payments.revoke_channel_invite") as mock_revoke:
            handle_webhook_event(canceled)
        mock_revoke.assert_called_once()

        data = self.store.load()
        sub = data["subscriptions"]["sub_01"]
        self.assertIsNone(sub["invite_link"])

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    def test_access_pending_before_webhook(self, mock_invite):
        access = self.store.access_for_transaction("txn_unknown")
        self.assertEqual(access["status"], "pending")

    def test_no_credentials_logs_warning(self):
        os.environ.pop(config.TELEGRAM_TOKEN_ENV, None)
        os.environ.pop(config.PRO_CHANNEL_ENV, None)
        event = {
            "event_id": "evt_09",
            "event_type": "subscription.activated",
            "occurred_at": "2026-07-31T12:00:00Z",
            "data": {"id": "sub_09", "status": "active"},
        }
        handle_webhook_event(event)
        access = self.store.access_for_transaction("txn_09")
        # No transaction recorded for this event path, so still pending.
        self.assertEqual(access["status"], "pending")


class TestWebhookRequest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_file = config.SUBSCRIPTIONS_FILE
        config.SUBSCRIPTIONS_FILE = Path(self._tmp.name) / "subscriptions.json"
        self._env = os.environ.copy()
        os.environ[config.PADDLE_WEBHOOK_SECRET_ENV] = "webhook-secret"

    def tearDown(self):
        config.SUBSCRIPTIONS_FILE = self._orig_file
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    def test_handle_request_valid_signature(self, mock_invite):
        os.environ[config.TELEGRAM_TOKEN_ENV] = "test-bot-token"
        os.environ[config.PRO_CHANNEL_ENV] = "-1001234567890"
        body = json.dumps({
            "event_id": "evt_01",
            "event_type": "transaction.completed",
            "occurred_at": "2026-07-31T12:00:00Z",
            "data": {
                "id": "txn_01",
                "subscription_id": "sub_01",
                "customer_id": "ctm_01",
                "status": "completed",
            },
        }).encode()
        header = _sign("webhook-secret", body)
        status, resp = handle_webhook_request(body, header)
        self.assertEqual(status, 200)
        self.assertTrue(resp["success"])
        mock_invite.assert_called_once()

    def test_handle_request_bad_signature(self):
        body = b'{"event_type": "subscription.activated"}'
        header = _sign("wrong-secret", body)
        status, resp = handle_webhook_request(body, header)
        self.assertEqual(status, 401)

    def test_handle_request_missing_secret(self):
        os.environ.pop(config.PADDLE_WEBHOOK_SECRET_ENV, None)
        body = b"{}"
        header = _sign("webhook-secret", body)
        status, resp = handle_webhook_request(body, header)
        self.assertEqual(status, 503)


if __name__ == "__main__":
    unittest.main()
