"""Unit tests for the Deepstream payment / fulfillment flow (Gumroad)."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from deepstream import config
from deepstream.payments import (
    SubscriptionStore,
    handle_webhook_event,
    handle_webhook_request,
)


def _sale_event(sale_id: str = "sale_01", sub_id: str = "sub_01", **overrides) -> dict:
    event = {
        "resource_name": "sale",
        "sale_id": sale_id,
        "sale_timestamp": "2026-07-31T12:00:00Z",
        "email": "pro@example.com",
        "subscription_id": sub_id,
        "product_id": "prod_01",
        "paid": "true",
        "refunded": "false",
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
        os.environ[config.GUMROAD_ACCESS_TOKEN_ENV] = "gumroad-token"
        os.environ[config.GUMROAD_PRODUCT_ID_ENV] = "prod_01"

    def tearDown(self):
        config.SUBSCRIPTIONS_FILE = self._orig_file
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_sale")
    def test_grant_on_verified_sale(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "id": "sale_01",
            "product_id": "prod_01",
            "paid": True,
            "refunded": False,
            "subscription_id": "sub_01",
            "email": "pro@example.com",
        }
        result = handle_webhook_event(_sale_event())
        self.assertIn("processed", result)
        mock_invite.assert_called_once()
        access = self.store.access_for_sale("sale_01")
        self.assertEqual(access["status"], "granted")
        self.assertEqual(access["invite_link"], "https://t.me/+abc123")

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_sale")
    def test_unverified_sale_is_rejected(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "id": "sale_01",
            "product_id": "other_product",
            "paid": True,
            "refunded": False,
            "subscription_id": "sub_01",
        }
        result = handle_webhook_event(_sale_event())
        self.assertIn("rejected", result)
        mock_invite.assert_not_called()
        self.assertEqual(self.store.access_for_sale("sale_01")["status"], "pending")

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_sale")
    def test_duplicate_sale_is_idempotent(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "id": "sale_01",
            "product_id": "prod_01",
            "paid": True,
            "refunded": False,
            "subscription_id": "sub_01",
        }
        handle_webhook_event(_sale_event())
        handle_webhook_event(_sale_event())
        self.assertEqual(mock_invite.call_count, 1)

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_sale")
    def test_revoke_on_refund(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "id": "sale_01",
            "product_id": "prod_01",
            "paid": True,
            "refunded": False,
            "subscription_id": "sub_01",
        }
        handle_webhook_event(_sale_event())

        refund = {
            "resource_name": "refund",
            "sale_id": "sale_01",
            "subscription_id": "sub_01",
            "sale_timestamp": "2026-08-01T12:00:00Z",
        }
        with mock.patch("deepstream.payments.revoke_channel_invite") as mock_revoke:
            result = handle_webhook_event(refund)
        mock_revoke.assert_called_once()
        self.assertIn("processed", result)

        data = self.store.load()
        sub = data["subscriptions"]["sub_01"]
        self.assertIsNone(sub["invite_link"])

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_sale")
    def test_revoke_on_subscription_ended(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "id": "sale_01",
            "product_id": "prod_01",
            "paid": True,
            "refunded": False,
            "subscription_id": "sub_01",
        }
        handle_webhook_event(_sale_event())

        ended = {
            "resource_name": "subscription_ended",
            "subscription_id": "sub_01",
            "created_at": "2026-08-01T12:00:00Z",
            "ended_reason": "cancelled",
        }
        with mock.patch("deepstream.payments.revoke_channel_invite") as mock_revoke:
            handle_webhook_event(ended)
        mock_revoke.assert_called_once()

    def test_access_pending_before_webhook(self):
        access = self.store.access_for_sale("sale_unknown")
        self.assertEqual(access["status"], "pending")

    def test_no_telegram_credentials_logs_warning(self):
        os.environ.pop(config.TELEGRAM_TOKEN_ENV, None)
        os.environ.pop(config.PRO_CHANNEL_ENV, None)
        with mock.patch("deepstream.payments.fetch_sale") as mock_fetch:
            mock_fetch.return_value = {
                "id": "sale_01",
                "product_id": "prod_01",
                "paid": True,
                "refunded": False,
                "subscription_id": "sub_01",
            }
            result = handle_webhook_event(_sale_event())
        self.assertIn("processed", result)
        access = self.store.access_for_sale("sale_01")
        self.assertEqual(access["status"], "pending")


class TestWebhookRequest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_file = config.SUBSCRIPTIONS_FILE
        config.SUBSCRIPTIONS_FILE = Path(self._tmp.name) / "subscriptions.json"
        self._env = os.environ.copy()
        os.environ[config.GUMROAD_ACCESS_TOKEN_ENV] = "gumroad-token"
        os.environ[config.GUMROAD_PRODUCT_ID_ENV] = "prod_01"
        os.environ[config.TELEGRAM_TOKEN_ENV] = "test-bot-token"
        os.environ[config.PRO_CHANNEL_ENV] = "-1001234567890"

    def tearDown(self):
        config.SUBSCRIPTIONS_FILE = self._orig_file
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_sale")
    def test_handle_request_form_encoded_sale(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "id": "sale_01",
            "product_id": "prod_01",
            "paid": True,
            "refunded": False,
            "subscription_id": "sub_01",
        }
        body = "resource_name=sale&sale_id=sale_01&email=pro%40example.com&subscription_id=sub_01&product_id=prod_01&paid=true&refunded=false".encode()
        status, resp = handle_webhook_request(body, "application/x-www-form-urlencoded")
        self.assertEqual(status, 200)
        self.assertTrue(resp["success"])
        mock_invite.assert_called_once()

    @mock.patch("deepstream.payments.create_channel_invite", return_value="https://t.me/+abc123")
    @mock.patch("deepstream.payments.fetch_sale")
    def test_handle_request_json_sale(self, mock_fetch, mock_invite):
        mock_fetch.return_value = {
            "id": "sale_01",
            "product_id": "prod_01",
            "paid": True,
            "refunded": False,
            "subscription_id": "sub_01",
        }
        body = json.dumps(_sale_event()).encode()
        status, resp = handle_webhook_request(body, "application/json")
        self.assertEqual(status, 200)
        self.assertTrue(resp["success"])
        mock_invite.assert_called_once()

    @mock.patch("deepstream.payments.fetch_sale")
    def test_handle_request_sale_lookup_failure_returns_500(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("API down")
        body = json.dumps(_sale_event()).encode()
        status, resp = handle_webhook_request(body, "application/json")
        self.assertEqual(status, 500)

    def test_handle_request_invalid_body(self):
        status, resp = handle_webhook_request(b"", "application/x-www-form-urlencoded")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
