"""verify_telegram.py — one-command Telegram setup health check.

Confirms the three things the payment flow depends on:
  1. ``DEEPSTREAM_BOT_TOKEN`` is set and the token is valid (getMe).
  2. The bot is an administrator of the private Pro channel
     (``DEEPSTREAM_PRO_CHANNEL_ID``) — getChatMember.
  3. The bot has invite-link permission (``can_invite_users``); with
     ``--test-invite`` this is proven end-to-end by minting and revoking a
     real invite link (the exact call the webhook makes).

Exit code 0 when everything passes, 1 otherwise.

Usage:
    python verify_telegram.py
    python verify_telegram.py --test-invite
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

from deepstream import config

API_BASE = "https://api.telegram.org"


def load_dotenv(path: Optional[Path] = None) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (no overrides)."""
    path = path or Path(__file__).resolve().parent / ".env"
    if not path.exists():
        return
    # utf-8-sig strips a Windows BOM that would otherwise prefix the first key.
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def telegram_api_call(token: str, method: str,
                      params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Call a Bot API method. Raises on network/HTTP errors."""
    url = f"{API_BASE}/bot{token}/{method}"
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _print_result(ok: bool, label: str) -> bool:
    prefix = "[ OK ]" if ok else "[FAIL]"
    print(f"{prefix} {label}")
    return ok


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test-invite", action="store_true",
        help="mint and revoke a real invite link to prove invite-link permission",
    )
    args = parser.parse_args(argv)

    load_dotenv()
    token = os.environ.get(config.TELEGRAM_TOKEN_ENV, "")
    pro_channel = os.environ.get(config.PRO_CHANNEL_ENV, "")
    public_channel = os.environ.get(config.TELEGRAM_CHANNEL_ENV, "")

    all_ok = True
    print("=== Deepstream Telegram verification ===")

    # 1. Token validity -----------------------------------------------------
    if not token:
        print(f"[FAIL] {config.TELEGRAM_TOKEN_ENV} is not set")
        return 1
    try:
        me = telegram_api_call(token, "getMe")
    except Exception as exc:  # network errors
        print(f"[FAIL] getMe request failed: {exc}")
        return 1
    if not me.get("ok"):
        print(f"[FAIL] getMe rejected the token: {me.get('description')}")
        return 1
    bot = me["result"]
    bot_id = bot["id"]
    all_ok &= _print_result(True, f"Bot token valid - @{bot.get('username')} (id {bot_id})")

    # 2. Pro channel admin status -------------------------------------------
    if not pro_channel:
        print(f"[WARN] {config.PRO_CHANNEL_ENV} is not set - skipping channel checks")
        all_ok = False
    else:
        try:
            member = telegram_api_call(token, "getChatMember", {
                "chat_id": pro_channel,
                "user_id": str(bot_id),
            })
        except Exception as exc:
            print(f"[FAIL] getChatMember request failed: {exc}")
            all_ok = False
        else:
            if not member.get("ok"):
                print(f"[FAIL] getChatMember rejected ({pro_channel}): {member.get('description')}")
                all_ok = False
            else:
                status = member["result"].get("status")
                can_invite = member["result"].get("can_invite_users")
                if status == "administrator":
                    all_ok &= _print_result(True, f"Bot is an administrator of Pro channel {pro_channel}")
                    if can_invite:
                        all_ok &= _print_result(True, "Invite-link permission (can_invite_users) enabled")
                    else:
                        all_ok &= _print_result(
                            False,
                            "Bot is admin but 'Invite users via link' permission is OFF "
                            "- enable it in channel settings",
                        )
                else:
                    all_ok &= _print_result(
                        False,
                        f"Bot is '{status}' in Pro channel - it must be an administrator",
                    )

    # 3. Public channel reachable (informational) ----------------------------
    if public_channel:
        try:
            chat = telegram_api_call(token, "getChat", {"chat_id": public_channel})
            if chat.get("ok"):
                print(f"[ OK ] Public channel reachable - {chat['result'].get('title')}")
            else:
                print(f"[WARN] Public channel lookup failed: {chat.get('description')}")
        except Exception as exc:
            print(f"[WARN] Public channel check failed: {exc}")

    # 4. Optional real invite-link round trip ---------------------------------
    if args.test_invite:
        if not (token and pro_channel):
            print("[SKIP] --test-invite needs both the bot token and Pro channel id")
        else:
            try:
                created = telegram_api_call(token, "createChatInviteLink", {
                    "chat_id": pro_channel,
                    "member_limit": 1,
                    "expire_date": int(time.time()) + 60,
                })
            except Exception as exc:
                print(f"[FAIL] createChatInviteLink request failed: {exc}")
                all_ok = False
            else:
                if not created.get("ok"):
                    print(f"[FAIL] createChatInviteLink rejected: {created.get('description')}")
                    all_ok = False
                else:
                    link = created["result"]["invite_link"]
                    all_ok &= _print_result(True, f"Invite link minted: {link}")
                    try:
                        revoked = telegram_api_call(token, "revokeChatInviteLink", {
                            "chat_id": pro_channel,
                            "invite_link": link,
                        })
                    except Exception as exc:
                        print(f"[FAIL] revokeChatInviteLink request failed: {exc}")
                        all_ok = False
                    else:
                        if revoked.get("ok"):
                            all_ok &= _print_result(True, "Invite link revoked - round trip works")
                        else:
                            all_ok &= _print_result(
                                False, f"revokeChatInviteLink rejected: {revoked.get('description')}"
                            )

    print()
    print("=== ALL CHECKS PASSED ===" if all_ok else "=== SOME CHECKS FAILED ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
