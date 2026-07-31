# Deepstream — Monetization Plan

## Strategy
Convert oceanographic data into statistically validated commodity signals,
deliver weekly via Telegram, charge a subscription for full trade setups.

The product is differentiated by **honest methodology**: signals are produced
walk-forward (no lookahead bias) and an out-of-sample track record is published
transparently on the landing site.

## Revenue Model
| Tier   | Price    | Delivery             | Content |
|--------|----------|----------------------|---------|
| Free   | $0       | Public TG channel    | Weekly position summary + confidence grades |
| Pro    | $29/mo   | Private TG channel   | Entry / Stop / Target + full track record |

## Architecture
```
deepstream/
  config.py            # asset pairs, thresholds, risk, delivery settings
  logging_setup.py     # structured rotating-file logging
  signal_engine.py     # correlation computation -> trade setups + grades
  track_record.py      # walk-forward out-of-sample performance replay
  telegram.py          # Telegram delivery of the weekly report
  server.py            # landing site + /latest_signal.json + /track_record.json
  cli.py               # `python -m deepstream {generate,track,run}`

signal_site/           # landing page (index.html, style.css, app.js)

tests/
  test_signal_engine.py
```

## CLI
```bash
python -m deepstream generate              # emit latest_signal.json
python -m deepstream track                 # emit track_record.json
python -m deepstream run                   # generate + track + refresh site
python -m deepstream run --skip-pipeline   # fast offline run
python -m deepstream.telegram              # deliver to Telegram (if configured)
python -m deepstream.server                # serve the site on :8080
```

## Weekly Run
```bash
./run_weekly.sh                # full pipeline + track record + delivery
./run_weekly.sh --skip-pipeline
```
Configure delivery by creating `.env` from `.env.template`:
```
DEEPSTREAM_BOT_TOKEN=<from @BotFather>
DEEPSTREAM_CHANNEL_ID=<private channel id>
```

## Honesty Guarantees (product differentiators)
- Signals are graded by absolute |r|: HIGH >= 0.70, MEDIUM >= 0.40, LOW >= 0.20.
- Only HIGH / MEDIUM signals are emitted as tradeable; LOW and NOISE are shown
  as "no trade".
- The track record replays the engine historically using only data available at
  each signal date — no hindsight. Published on the site.
- Confidence thresholds, stop/target levels, and holding periods are
  config-driven and auditable in `deepstream/config.py`.

## Remaining Launch Steps
1. **Payment integration (implemented).** Paddle (Merchant of Record) handles
   the $29/mo Pro subscription via Paddle.js overlay checkout. Webhooks arrive
   at `POST /webhooks/paddle`, are HMAC-verified in `deepstream/payments.py`,
   and on a successful subscription the bot mints a single-use invite link to
   the private Pro Telegram channel. The customer is redirected to
   `success.html?transaction_id=...`, which polls `/api/access` and shows the
   invite link. Revocation (`subscription.canceled`/`paused`) revokes the link.
   **Setup still required:** create the Paddle product + price + client token +
   notification destination, and fill in the Paddle vars in `.env`.
2. Create the private Telegram channel, add the bot as admin (invite-link
   permission), set `DEEPSTREAM_PRO_CHANNEL_ID`; fill in the rest of `.env`.
3. Run `./run_weekly.sh` and confirm delivery.

### Go-live checklist for payments
- [ ] `PADDLE_ENV=live`, `PADDLE_CLIENT_TOKEN`, `PADDLE_PRICE_ID`, `PADDLE_WEBHOOK_SECRET` set
- [ ] Webhook URL = `https://<your-domain>/webhooks/paddle`, subscribed to
      `subscription.created/activated/updated/canceled/paused/past_due` and `transaction.completed`
- [ ] `DEEPSTREAM_BOT_TOKEN` + `DEEPSTREAM_PRO_CHANNEL_ID` set; bot is admin of the Pro channel
- [ ] Sandbox test card `4242 4242 4242 4242` confirms end-to-end invite delivery
