"""Tests for the hardened HTTP server (security headers, CORS, rate limiting,
input validation)."""

import http.client
import http.server
import json
import os
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from deepstream import config
from deepstream.payments import CashfreeError
from deepstream.server import DeepstreamHandler


class ServerTestCase(unittest.TestCase):
    """Boot a real DeepstreamHandler server on an ephemeral port."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        # Redirect subscription store writes away from the repo.
        cls._orig_subscriptions = config.SUBSCRIPTIONS_FILE
        config.SUBSCRIPTIONS_FILE = Path(cls._tmp.name) / "subscriptions.json"

        cls._env = os.environ.copy()
        # No site configured by default → cross-origin reads refused.
        os.environ.pop(config.CASHFREE_SITE_URL_ENV, None)

        class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

        cls.httpd = ThreadingServer(("127.0.0.1", 0), DeepstreamHandler)
        cls.port = cls.httpd.server_address[1]
        cls._thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        config.SUBSCRIPTIONS_FILE = cls._orig_subscriptions
        os.environ.clear()
        os.environ.update(cls._env)
        cls._tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        payload = resp.read()
        conn.close()
        return resp.status, resp.getheaders(), payload


class TestSecurityHeaders(ServerTestCase):
    def test_json_endpoint_has_security_headers(self):
        status, headers, _ = self.request("GET", "/api/payments_config")
        hdrs = dict(headers)
        self.assertEqual(status, 200)
        self.assertEqual(hdrs["X-Content-Type-Options"], "nosniff")
        self.assertEqual(hdrs["X-Frame-Options"], "DENY")
        self.assertIn("strict-origin-when-cross-origin", hdrs["Referrer-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", hdrs)

    def test_static_page_has_security_headers(self):
        status, headers, _ = self.request("GET", "/")
        hdrs = dict(headers)
        self.assertEqual(status, 200)
        self.assertEqual(hdrs["X-Content-Type-Options"], "nosniff")
        self.assertEqual(hdrs["X-Frame-Options"], "DENY")

    def test_cors_refused_without_configured_site(self):
        # No CASHFREE_SITE_URL → cross-origin requests must not be granted.
        status, headers, _ = self.request(
            "GET", "/api/payments_config",
            headers={"Origin": "https://evil.example"},
        )
        hdrs = dict(headers)
        self.assertNotIn("Access-Control-Allow-Origin", hdrs)

    def test_cors_refused_for_untrusted_origin(self):
        os.environ[config.CASHFREE_SITE_URL_ENV] = "https://deepstreamofficial.netlify.app"
        try:
            status, headers, _ = self.request(
                "GET", "/api/payments_config",
                headers={"Origin": "https://evil.example"},
            )
            self.assertNotIn("Access-Control-Allow-Origin", dict(headers))
        finally:
            os.environ.pop(config.CASHFREE_SITE_URL_ENV, None)

    def test_cors_granted_for_trusted_origin(self):
        os.environ[config.CASHFREE_SITE_URL_ENV] = "https://deepstreamofficial.netlify.app"
        try:
            status, headers, _ = self.request(
                "GET", "/api/payments_config",
                headers={"Origin": "https://deepstreamofficial.netlify.app"},
            )
            hdrs = dict(headers)
            self.assertEqual(hdrs["Access-Control-Allow-Origin"],
                             "https://deepstreamofficial.netlify.app")
        finally:
            os.environ.pop(config.CASHFREE_SITE_URL_ENV, None)


class TestInputValidation(ServerTestCase):
    def test_create_order_rejects_invalid_email(self):
        status, _, body = self.request(
            "POST", "/api/create-order",
            body=json.dumps({"customer_email": "not-an-email"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)
        self.assertIn("customer_email", json.loads(body)["error"])

    def test_create_order_rejects_missing_email(self):
        status, _, body = self.request(
            "POST", "/api/create-order",
            body=json.dumps({"customer_email": ""}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)

    def test_create_order_rejects_oversized_phone(self):
        status, _, _ = self.request(
            "POST", "/api/create-order",
            body=json.dumps({"customer_email": "ok@example.com",
                             "customer_phone": "9" * 21}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)

    def test_create_order_rejects_missing_phone(self):
        """Cashfree requires a phone — an empty one must fail with 400."""
        status, _, body = self.request(
            "POST", "/api/create-order",
            body=json.dumps({"customer_email": "ok@example.com"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)
        self.assertIn("customer_phone", json.loads(body)["error"])

    def test_create_order_normalizes_phone_formatting(self):
        """Spaces/plus/dashes in the phone are stripped before validation."""
        with mock.patch("deepstream.server.create_cashfree_order") as mock_create:
            mock_create.return_value = {"order_id": "ds_x",
                                        "payment_session_id": "s",
                                        "order_status": "ACTIVE"}
            status, _, body = self.request(
                "POST", "/api/create-order",
                body=json.dumps({"customer_email": "ok@example.com",
                                 "customer_phone": "+91 98765-43210"}),
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(status, 200)
            phone = mock_create.call_args[0][1]
            self.assertEqual(phone, "919876543210")

    def test_access_rejects_invalid_order_id(self):
        status, _, _ = self.request("GET", "/api/access?order_id=../../../etc/passwd")
        self.assertEqual(status, 400)

    def test_access_rejects_malformed_order_id(self):
        status, _, _ = self.request("GET", "/api/access?order_id=ds_not-hex")
        self.assertEqual(status, 400)

    def test_access_accepts_well_formed_order_id(self):
        status, _, body = self.request("GET", "/api/access?order_id=ds_0123456789abcdef")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "pending")


class TestCreateOrderErrors(ServerTestCase):
    @mock.patch(
        "deepstream.server.create_cashfree_order",
        side_effect=CashfreeError(
            "api Request Failed", status=500, code="request_failed"
        ),
    )
    def test_provider_rejection_includes_detail(self, mock_create):
        """502 from Cashfree must surface the provider's real message."""
        status, _, body = self.request(
            "POST", "/api/create-order",
            body=json.dumps({"customer_email": "ok@example.com",
                             "customer_phone": "9876543210"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 502)
        payload = json.loads(body)
        self.assertEqual(payload["error"], "order creation failed")
        self.assertIn("api Request Failed", payload["detail"])

    @mock.patch(
        "deepstream.server.create_cashfree_order",
        side_effect=RuntimeError("boom"),
    )
    def test_unexpected_error_stays_generic(self, mock_create):
        """Non-provider failures must not leak internals to the client."""
        status, _, body = self.request(
            "POST", "/api/create-order",
            body=json.dumps({"customer_email": "ok@example.com",
                             "customer_phone": "9876543210"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 502)
        payload = json.loads(body)
        self.assertEqual(payload["error"], "order creation failed")
        self.assertNotIn("detail", payload)


class TestBodyLimit(ServerTestCase):
    def test_oversized_body_rejected(self):
        # Declare an oversized Content-Length; the server rejects it before the
        # body is streamed, so send headers only (sending 1 MiB+ would trip a
        # BrokenPipeError once the server closes the connection).
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.putrequest("POST", "/api/create-order")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(1024 * 1024 + 1))
        conn.endheaders()
        resp = conn.getresponse()
        conn.close()
        self.assertEqual(resp.status, 413)


if __name__ == "__main__":
    unittest.main()
