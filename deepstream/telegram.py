"""Telegram delivery for Deepstream signals."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Optional

from deepstream import config
from deepstream.logging_setup import setup_logging
from deepstream.signal_engine import compute_all_signals, load_params

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
    """Send ``text`` to a Telegram chat. Returns the raw API response body.

    Note: uses Telegram's legacy Markdown parse mode, so message content
    must not contain unescaped ``_ * [ ``` characters. Pair names in
    ``config.PAIRS`` are safe today; escape if content ever changes.
    """
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


def format_daily_report(signals: list[dict[str, Any]], today: str | None = None) -> str:
    """Render the daily position update for the private Pro channel.

    Unlike the weekly report this is delivered every day and reflects the
    freshly recomputed signal (current correlation and recent price moves).
    Full entry / stop / target levels are included — this is Pro content.
    """
    active = [
        s for s in signals
        if s.get("status") == "ACTIVE" and s.get("direction") not in ("NONE",)
    ]
    date_str = today or datetime.utcnow().strftime("%Y-%m-%d")

    lines = [f"DEEPSTREAM — Daily Position Update · {date_str}\n"]
    if not active:
        lines.append("No tradeable setups today. Standing aside is a position.")
    else:
        for s in active:
            grade = s["confidence"]
            tag = {"HIGH": "[HIGH]", "MEDIUM": "[MEDIUM]", "LOW": "[LOW]"}.get(grade, "")
            arrow = "[LONG]" if s["direction"] == "LONG" else "[SHORT]"
            lines.append(f"{tag} {s['pair']}")
            lines.append(
                f"  {arrow} Entry {s['entry']} | SL {s['stop_loss']} | TP {s['take_profit']}"
            )
            lines.append(
                f"  r = {s['pearson_r']:.3f} | lead {s['lag_days']}d | {s['confidence']}"
            )
            if s.get("price_change_pct") is not None:
                lines.append(
                    f"  Price change: {s['price_change_pct']:+.2f}% | "
                    f"Ocean move: {float(s.get('ocean_change') or 0):+.4f}"
                )
            lines.append("")

    lines.append("Next update tomorrow. Weekly track record published every Monday.")
    return "\n".join(lines)


def deliver_daily(verbose: bool = False) -> int:
    """Recompute signals from the current data and send a daily position
    update to the private Pro channel.

    Unlike the weekly flow this never touches the published site assets or
    the track record — it is a lightweight daily status for subscribers.
    Returns 0 on delivery, 1 when misconfigured or the send fails.
    """
    global logger
    logger = setup_logging(verbose=verbose)

    params = load_params()
    signals = [s.to_dict() for s in compute_all_signals(params)]
    report = format_daily_report(signals)

    token = os.environ.get(config.TELEGRAM_TOKEN_ENV)
    pro_channel = os.environ.get(config.PRO_CHANNEL_ENV)
    if not (token and pro_channel):
        logger.info(
            "Daily update needs %s and %s — printing report:\n%s",
            config.TELEGRAM_TOKEN_ENV, config.PRO_CHANNEL_ENV, report,
        )
        return 1

    try:
        send_telegram(token, pro_channel, report)
    except Exception as exc:  # network / API errors must not crash the run
        logger.error("Daily Pro channel delivery failed: %s", exc)
        return 1
    logger.info("Daily update delivered to Pro channel %s", pro_channel)
    return 0


if __name__ == "__main__":
    raise SystemExit(deliver(verbose=True))
