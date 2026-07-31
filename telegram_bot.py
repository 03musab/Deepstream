import json
import os
import sys

SIGNAL_FILE = "latest_signal.json"

BOT_TOKEN_ENV = "DEEPSTREAM_BOT_TOKEN"
CHANNEL_ID_ENV = "DEEPSTREAM_CHANNEL_ID"

def format_signal_report(signals):
    lines = [
        "**Deepstream Weekly Report**\n"
    ]

    active = [s for s in signals if s.get("status") == "ACTIVE"]
    if not active:
        lines.append("No active signals this week.")
        return "\n".join(lines)

    for s in active:
        emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔵", "NOISE": "⚪"}.get(s["confidence"], "⚪")
        direction_emoji = "🔼" if s["direction"] == "LONG" else "🔽"
        lines.append(
            f"{emoji} **{s['pair']}**\n"
            f"  {direction_emoji} {s['direction']} | Entry: ${s['entry']}\n"
            f"  SL: ${s['stop_loss']} | TP: ${s['take_profit']}\n"
            f"  Confidence: {s['confidence']} (r={s['pearson_r']}) | Lag: {s['lag_days']}d\n"
        )

    return "\n".join(lines)

def send_telegram(bot_token, chat_id, text):
    import urllib.request
    import urllib.parse

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }).encode()

    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode()

def main():
    if not os.path.exists(SIGNAL_FILE):
        print("No signal file found. Run generate_signal.py first.")
        sys.exit(1)

    with open(SIGNAL_FILE) as f:
        data = json.load(f)

    report = format_signal_report(data["signals"])

    bot_token = os.environ.get(BOT_TOKEN_ENV)
    chat_id = os.environ.get(CHANNEL_ID_ENV)

    if bot_token and chat_id:
        print("Sending to Telegram...")
        try:
            result = send_telegram(bot_token, chat_id, report)
            print("Sent successfully.")
        except Exception as e:
            print(f"Telegram send failed: {e}")
    else:
        print("=== SIGNAL REPORT (preview) ===")
        print(report)
        print(f"\nSet {BOT_TOKEN_ENV} and {CHANNEL_ID_ENV} env vars to enable Telegram delivery.")

if __name__ == "__main__":
    main()
