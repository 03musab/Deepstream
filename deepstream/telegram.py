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


def format_signal_summary(signals: list[dict[str, Any]]) -> str:
    """Render the public weekly summary — direction and grades only.

    Deliberately omits entry / stop / target levels: those are Pro content and
    are delivered only to the private Pro channel (``format_signal_report``).
    """
    active = [
        s for s in signals
        if s.get("status") == "ACTIVE" and s.get("direction") not in ("NONE",)
    ]

    lines = ["DEEPSTREAM — Weekly Signal Summary\n"]
    if not active:
        lines.append("No tradeable signals this week. Standing aside is a position.")
    else:
        for s in active:
            grade = s["confidence"]
            tag = {"HIGH": "[HIGH]", "MEDIUM": "[MEDIUM]", "LOW": "[LOW]"}.get(grade, "")
            arrow = "[LONG]" if s["direction"] == "LONG" else "[SHORT]"
            lines.append(
                f"{tag} {s['pair']} — {arrow} "
                f"r = {s['pearson_r']:.3f} | lead {s['lag_days']}d | "
                f"{s['confidence']} confidence"
            )
        lines.append("")
        lines.append("Full setups (entry · stop · target) are available to Pro subscribers.")
    lines.append("Methodology: walk-forward, out-of-sample. See website for the track record.")
    return "\n".join(lines)


def format_signal_report(signals: list[dict[str, Any]]) -> str:
    """Render the full weekly report for Pro subscribers (includes levels)."""
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

    signals = data.get("signals", [])
    summary = format_signal_summary(signals)
    report = format_signal_report(signals)

    token = os.environ.get(config.TELEGRAM_TOKEN_ENV)
    public_channel = os.environ.get(config.TELEGRAM_CHANNEL_ENV)
    pro_channel = os.environ.get(config.PRO_CHANNEL_ENV)

    # Delivery split:
    #   public channel → summary (direction + grades, no levels)
    #   Pro channel    → full setups (entry · stop · target)
    if not (token and (public_channel or pro_channel)):
        logger.info(
            "Telegram not configured — printing summary:\n%s\n\nFull report:\n%s",
            summary, report,
        )
        return 0

    delivered = 0
    if public_channel:
        try:
            send_telegram(token, public_channel, summary)
            logger.info("Summary delivered to public channel %s", public_channel)
            delivered += 1
        except Exception as exc:  # network / API errors must not crash the run
            logger.error("Public channel delivery failed: %s", exc)
    if pro_channel:
        try:
            send_telegram(token, pro_channel, report)
            logger.info("Full report delivered to Pro channel %s", pro_channel)
            delivered += 1
        except Exception as exc:  # network / API errors must not crash the run
            logger.error("Pro channel delivery failed: %s", exc)
    if delivered == 0:
        logger.error("Telegram delivery failed: no message sent")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(deliver(verbose=True))
