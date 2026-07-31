"""Unit tests for Deepstream Telegram delivery (public summary vs Pro report)."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from deepstream import config
from deepstream.telegram import (
    deliver,
    format_signal_report,
    format_signal_summary,
    send_telegram,
)


def _signals():
    return [
        {
            "pair_id": 2,
            "pair": "Atlantic Chlorophyll → Tuna Price",
            "direction": "SHORT",
            "confidence": "HIGH",
            "pearson_r": -0.7754,
            "lag_days": 30,
            "entry": 12.84,
            "stop_loss": 13.48,
            "take_profit": 11.81,
            "status": "ACTIVE",
        },
        {
            "pair_id": 1,
            "pair": "ENSO — Pacific Sea Surface Temperature → Copper Futures",
            "direction": "NONE",
            "confidence": "LOW",
            "pearson_r": -0.3489,
            "lag_days": 56,
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
            "status": "NO_TRADE",
        },
    ]


class TestFormatting(unittest.TestCase):
    def test_summary_omits_levels(self):
        text = format_signal_summary(_signals())
        self.assertIn("SHORT", text)
        self.assertIn("Atlantic Chlorophyll", text)
        self.assertIn("r = -0.775", text)
        # Pro-only content must never leak into the public summary.
        self.assertNotIn("12.84", text)
        self.assertNotIn("13.48", text)
        self.assertNotIn("11.81", text)
        self.assertNotIn("Entry", text)

    def test_summary_no_tradeable(self):
        text = format_signal_summary([
            {"status": "NO_TRADE", "direction": "NONE", "confidence": "LOW",
             "pearson_r": 0.03, "lag_days": 110},
        ])
        self.assertIn("No tradeable signals", text)
        self.assertNotIn("Entry", text)

    def test_report_includes_levels(self):
        text = format_signal_report(_signals())
        self.assertIn("Entry 12.84", text)
        self.assertIn("SL 13.48", text)
        self.assertIn("TP 11.81", text)


class TestDeliver(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_file = config.SIGNAL_FILE
        config.SIGNAL_FILE = Path(self._tmp.name) / "latest_signal.json"
        config.SIGNAL_FILE.write_text(
            json.dumps({"signals": _signals()}), encoding="utf-8"
        )
        self._env = os.environ.copy()
        os.environ[config.TELEGRAM_TOKEN_ENV] = "test-bot-token"
        os.environ[config.TELEGRAM_CHANNEL_ENV] = "-100public"
        os.environ[config.PRO_CHANNEL_ENV] = "-100pro"

    def tearDown(self):
        config.SIGNAL_FILE = self._orig_file
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    @mock.patch("deepstream.telegram.send_telegram", return_value="{}")
    def test_deliver_splits_public_and_pro(self, mock_send):
        code = deliver()
        self.assertEqual(code, 0)
        self.assertEqual(mock_send.call_count, 2)
        # send_telegram is called positionally: (bot_token, chat_id, text).
        self.assertEqual(mock_send.call_args_list[0].args[1], "-100public")
        self.assertEqual(mock_send.call_args_list[1].args[1], "-100pro")
        public_text = mock_send.call_args_list[0].args[2]
        pro_text = mock_send.call_args_list[1].args[2]
        # Summary goes public (no levels), full report goes to Pro.
        self.assertNotIn("Entry", public_text)
        self.assertNotIn("12.84", public_text)
        self.assertIn("Entry 12.84", pro_text)

    @mock.patch("deepstream.telegram.send_telegram", return_value="{}")
    def test_deliver_skips_unset_pro_channel(self, mock_send):
        os.environ.pop(config.PRO_CHANNEL_ENV, None)
        code = deliver()
        self.assertEqual(code, 0)
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args_list[0].args[1], "-100public")

    @mock.patch("deepstream.telegram.send_telegram", return_value="{}")
    def test_deliver_skips_unset_public_channel(self, mock_send):
        os.environ.pop(config.TELEGRAM_CHANNEL_ENV, None)
        code = deliver()
        self.assertEqual(code, 0)
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args_list[0].args[1], "-100pro")

    def test_deliver_not_configured_prints(self):
        os.environ.pop(config.TELEGRAM_TOKEN_ENV, None)
        with mock.patch("deepstream.telegram.send_telegram") as mock_send:
            code = deliver()
        self.assertEqual(code, 0)
        mock_send.assert_not_called()

    def test_deliver_missing_signal_file(self):
        config.SIGNAL_FILE.unlink()
        self.assertEqual(deliver(), 1)


class TestSendTelegram(unittest.TestCase):
    @mock.patch("deepstream.telegram.urllib.request.urlopen")
    def test_send_telegram_builds_request(self, mock_urlopen):
        resp = mock.MagicMock()
        resp.read.return_value = b'{"ok": true}'
        mock_urlopen.return_value.__enter__.return_value = resp
        result = send_telegram("bot-token", "-100chan", "hello")
        self.assertEqual(result, '{"ok": true}')
        req = mock_urlopen.call_args.args[0]
        self.assertIn("/botbot-token/sendMessage", req.full_url)
        self.assertEqual(req.data.decode(), "chat_id=-100chan&text=hello&parse_mode=Markdown")


if __name__ == "__main__":
    unittest.main()
