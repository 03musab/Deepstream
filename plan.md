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
| Free   | ₹0       | Public TG channel    | Weekly position summary + confidence grades (no levels) |
| Pro    | ₹2,499/mo| Private TG channel   | Entry / Stop / Target + full track record |

### Delivery split (implemented)
`deepstream.telegram` sends two messages each week:
- **Public channel** (`DEEPSTREAM_CHANNEL_ID`) — `format_signal_summary`:
  direction + confidence grades only. Entry/stop/target are never included,
  so free subscribers see the signal exists but not the setup.
- **Private Pro channel** (`DEEPSTREAM_PRO_CHANNEL_ID`) — `format_signal_report`:
  full setups with entry / stop / target.

Either channel may be unset; delivery to a configured channel still succeeds.
Pro access itself is still gated by the paid invite-link flow (Cashfree).

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
1. **Payment integration (implemented).** Cashfree Payment Gateway handles the
   ₹2,499/mo Pro membership. A visitor enters their email on the landing page;
   `POST /api/create-order` creates a Cashfree order and returns a
   `payment_session_id`, which the Cashfree JS SDK (`cashfree.checkout`)
   renders as a hosted/drop-in checkout. Cashfree sends **signed** webhooks to
   `POST /webhooks/cashfree`; `deepstream/payments.py` verifies the
   `x-webhook-signature` (HMAC-SHA256) before doing anything. On a verified
   `ORDER_PAID` (re-checked against the Cashfree API) the bot mints a
   single-use invite link to the private Pro Telegram channel, keyed by
   `order_id`. The checkout redirects to `success.html`, which polls
   `/api/access?order_id=...` and shows the invite link. Revocation
   (`REFUND_STATUS`, `ORDER_FAILED`, `ORDER_CANCELLED`) revokes the link.
   **Hosting:** the site is static on Netlify; the payment backend is a set of
   Netlify Functions (`netlify/functions/`) that mirror `deepstream/payments.py`
   and store order state in Netlify Blobs. The Python server remains the local
   dev backend (`python -m deepstream.server`).
   **Setup still required:** create the Cashfree account (sandbox keys work
   immediately; production needs KYC + ~24–48h activation), set the webhook
   URL + secret, whitelist your domain, and fill in the vars in `.env` /
   Netlify environment variables (see `.env.example`).
2. Create the private Telegram channel, add the bot as admin (invite-link
   permission), set `DEEPSTREAM_PRO_CHANNEL_ID`.
3. Run `./run_weekly.sh` and confirm delivery.

### Go-live checklist for payments
- [ ] Cashfree sandbox credentials (`CASHFREE_CLIENT_ID` / `CASHFREE_CLIENT_SECRET`) set
- [ ] `CASHFREE_WEBHOOK_SECRET` set; webhook URL registered in the Cashfree
      dashboard for `ORDER_PAID`, `ORDER_FAILED`, `ORDER_CANCELLED`,
      `REFUND_STATUS` → `https://<your-domain>/webhooks/cashfree`
- [ ] Domain whitelisted in Cashfree dashboard (production)
- [ ] `DEEPSTREAM_BOT_TOKEN` + `DEEPSTREAM_PRO_CHANNEL_ID` set; bot is admin of the Pro channel
- [ ] `CASHFREE_SITE_URL` points at the deployed site
- [ ] Test order in sandbox (test cards: CVV `123`, OTP `111000`, UPI
      `testsuccess@gocash`) confirms end-to-end invite delivery
- [ ] Confirm which webhook signature variant Cashfree delivers (body-only vs
      timestamp+body) against a real dashboard test event — the code accepts
      both, but verify before going live
- [ ] Production KYC submitted; `CASHFREE_ENV=production` after activation

> **Billing note:** the Pro tier is sold in INR (₹2,499/mo) as a monthly
> order — each successful payment grants 30 days via a fresh invite link, and
> renewals are new orders from the same customer. Since billing is already
> INR, a future upgrade can adopt Cashfree's native auto-recurring
> subscriptions (UPI AutoPay / eNACH).
