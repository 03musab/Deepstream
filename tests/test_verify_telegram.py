"""Unit tests for the Telegram verification helper script."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import verify_telegram
from deepstream import config

# The real function, captured before setUp replaces it with a mock.
_REAL_LOAD_DOTENV = verify_telegram.load_dotenv


def _fake_api(me_ok=True, member_status="administrator", can_invite=True,
              invite_ok=True, chat_ok=True):
    """Build a fake telegram_api_call with configurable responses."""
    def fake(token, method, params=None):
        if method == "getMe":
            if not me_ok:
                return {"ok": False, "description": "Unauthorized"}
            return {"ok": True, "result": {"id": 42, "username": "deepstream_bot"}}
        if method == "getChatMember":
            if member_status is None:
                return {"ok": False, "description": "chat not found"}
            return {"ok": True, "result": {"status": member_status, "can_invite_users": can_invite}}
        if method == "getChat":
            if not chat_ok:
                return {"ok": False, "description": "chat not found"}
            return {"ok": True, "result": {"title": "Deepstream Public"}}
        if method == "createChatInviteLink":
            if not invite_ok:
                return {"ok": False, "description": "not enough rights"}
            return {"ok": True, "result": {"invite_link": "https://t.me/+abc123"}}
        if method == "revokeChatInviteLink":
            return {"ok": True, "result": {}}
        return {"ok": False, "description": "unknown method"}
    return fake


def _run(argv=None):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        # Pass [] explicitly so argparse does not read the unittest runner's
        # sys.argv (which would fail with unrecognized arguments).
        rc = verify_telegram.main(argv if argv is not None else [])
    return rc, out.getvalue()


class TestVerifyTelegram(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.copy()
        os.environ[config.TELEGRAM_TOKEN_ENV] = "123:ABC"
        os.environ[config.PRO_CHANNEL_ENV] = "-1001234567890"
        os.environ[config.TELEGRAM_CHANNEL_ENV] = "-100111"
        # Keep a stray .env on the repo from changing test behavior.
        verify_telegram.load_dotenv = mock.MagicMock()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        verify_telegram.load_dotenv = _REAL_LOAD_DOTENV

    @mock.patch("verify_telegram.telegram_api_call")
    def test_all_checks_pass(self, mock_api):
        mock_api.side_effect = _fake_api()
        rc, out = _run()
        self.assertEqual(rc, 0)
        self.assertIn("ALL CHECKS PASSED", out)
        self.assertIn("Bot token valid", out)
        self.assertIn("administrator of Pro channel", out)
        self.assertIn("Invite-link permission", out)

    @mock.patch("verify_telegram.telegram_api_call")
    def test_missing_token_fails_fast(self, mock_api):
        os.environ.pop(config.TELEGRAM_TOKEN_ENV, None)
        rc, out = _run()
        self.assertEqual(rc, 1)
        self.assertIn("not set", out)
        mock_api.assert_not_called()

    @mock.patch("verify_telegram.telegram_api_call")
    def test_invalid_token_fails(self, mock_api):
        mock_api.side_effect = _fake_api(me_ok=False)
        rc, out = _run()
        self.assertEqual(rc, 1)
        self.assertIn("rejected the token", out)

    @mock.patch("verify_telegram.telegram_api_call")
    def test_bot_not_admin_fails(self, mock_api):
        mock_api.side_effect = _fake_api(member_status="member")
        rc, out = _run()
        self.assertEqual(rc, 1)
        self.assertIn("must be an administrator", out)

    @mock.patch("verify_telegram.telegram_api_call")
    def test_missing_invite_permission_fails(self, mock_api):
        mock_api.side_effect = _fake_api(can_invite=False)
        rc, out = _run()
        self.assertEqual(rc, 1)
        self.assertIn("Invite users via link", out)

    @mock.patch("verify_telegram.telegram_api_call")
    def test_test_invite_round_trip(self, mock_api):
        mock_api.side_effect = _fake_api()
        rc, out = _run(["--test-invite"])
        self.assertEqual(rc, 0)
        self.assertIn("Invite link minted", out)
        self.assertIn("round trip works", out)
        methods = [call.args[1] for call in mock_api.call_args_list]
        self.assertIn("createChatInviteLink", methods)
        self.assertIn("revokeChatInviteLink", methods)

    @mock.patch("verify_telegram.telegram_api_call")
    def test_test_invite_fails_without_permission(self, mock_api):
        mock_api.side_effect = _fake_api(invite_ok=False)
        rc, out = _run(["--test-invite"])
        self.assertEqual(rc, 1)
        self.assertIn("createChatInviteLink rejected", out)

    @mock.patch("verify_telegram.telegram_api_call")
    def test_missing_pro_channel_warns(self, mock_api):
        os.environ.pop(config.PRO_CHANNEL_ENV, None)
        mock_api.side_effect = _fake_api()
        rc, out = _run()
        self.assertEqual(rc, 1)
        self.assertIn("skipping channel checks", out)

    def test_load_dotenv_parses_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "NEW_VAR=from-file\n# comment\nEMPTY=\nEXISTING_VAR=should-not-override\n",
                encoding="utf-8",
            )
            os.environ["EXISTING_VAR"] = "original"
            _REAL_LOAD_DOTENV(env_file)
            self.assertEqual(os.environ.get("NEW_VAR"), "from-file")
            self.assertNotIn("EMPTY", os.environ)
            self.assertEqual(os.environ.get("EXISTING_VAR"), "original")


if __name__ == "__main__":
    unittest.main()
