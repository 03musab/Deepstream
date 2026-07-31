#!/bin/bash
# Deepstream weekly signal runner
# Run this every Monday morning to generate and deliver signals
#
# Usage: ./run_weekly.sh
#
# Before first use, create a Telegram bot:
#   1. Open Telegram, message @BotFather, send /newbot
#   2. Copy the token, add to .env as DEEPSTREAM_BOT_TOKEN
#   3. Create a private channel, add bot as admin
#   4. Post any message, then visit:
#      https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
#   5. Copy the chat_id from the response, add to .env as DEEPSTREAM_CHANNEL_ID
#   6. Run: cp .env.template .env && nano .env

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load env vars if .env exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

echo "=== Deepstream Weekly Run: $(date) ==="

# Step 1: Generate signals
python3 generate_signal.py

# Step 2: Copy to site for preview
cp latest_signal.json signal_site/

# Step 3: Deliver via Telegram (if configured)
if [ -n "$DEEPSTREAM_BOT_TOKEN" ] && [ -n "$DEEPSTREAM_CHANNEL_ID" ]; then
    python3 telegram_bot.py
    echo "Signals delivered to Telegram."
else
    echo "Telegram not configured. Set DEEPSTREAM_BOT_TOKEN and DEEPSTREAM_CHANNEL_ID in .env"
fi

echo "=== Done ==="
