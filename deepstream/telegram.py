"""Telegram delivery for Deepstream signals."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Optional

from deepstream import config
from deepstream.logging_setup import setup_logging

logger = setup_logging()


def format_signal_report(signals: list[dict[str, Any]]) -> str:
    """Render the weekly report for Telegram subscribers."""
    active = [
        s for s in signals
        if s.get("status") == "ACTIVE" and s.get("direction") not in ("NONE",)
    ]

    lines = ["DEEPSTREAM — Weekly Signal Report\n"]
    if not active:
        lines.append("No tradeable signals this week. Standing aside is a position.")
        return "\n".join(lines)

    for s in active:
        grade = s["confidence"]
        tag = {"HIGH": "[HIGH]", "MEDIUM": "[MEDIUM]", "LOW": "[LOW]"}.get(grade, "")
        arrow = "[LONG]" if s["direction"] == "LONG" else "[SHORT]"
        lines.extend([
            f"{tag} {s['pair']}",
            f"  {arrow} Entry {s['entry']} | SL {s['stop_loss']} | TP {s['take_profit']}",
            f"  r = {s['pearson_r']:.3f} | lead {s['lag_days']}d | {s['confidence']} confidence",
            "",
        ])

    lines.append("Methodology: walk-forward, out-of-sample. See website for full track record.")
    return "\n".join(lines)


def send_telegram(bot_token: str, chat_id: str, text: str) -> Optional[str]:
    """Send ``text`` to a Telegram chat. Returns the raw API response body."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode()


def deliver(verbose: bool = False) -> int:
    """Read the latest signal file and deliver it to Telegram if configured."""
    global logger
    logger = setup_logging(verbose=verbose)

    if not config.SIGNAL_FILE.exists():
        logger.error("No signal file found. Run `deepstream generate` first.")
        return 1

    with open(config.SIGNAL_FILE) as f:
        data = json.load(f)

    report = format_signal_report(data.get("signals", []))

    token = os.environ.get(config.TELEGRAM_TOKEN_ENV)
    channel = os.environ.get(config.TELEGRAM_CHANNEL_ENV)

    if not (token and channel):
        logger.info("Telegram not configured — printing report:\n%s", report)
        return 0

    try:
        send_telegram(token, channel, report)
        logger.info("Report delivered to Telegram channel %s", channel)
    except Exception as exc:  # network / API errors must not crash the run
        logger.error("Telegram delivery failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(deliver(verbose=True))
