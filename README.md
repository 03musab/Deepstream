# Deepstream

**Ocean-data commodity signal platform.** Deepstream converts oceanographic indicators — sea-surface temperature, chlorophyll, and chemical plumes — into statistically validated weekly commodity trade setups (Copper, Tuna, Crude Oil), delivered via Telegram and monetized through a paid Pro tier.

The product is differentiated by **honest methodology**: signals are produced walk-forward (no lookahead bias), Granger-causality tested over 20 years of history, and an out-of-sample track record is published transparently on the landing site.

---

## Current Status

| Area | Status |
|------|--------|
| Signal engine (3 asset pairs) | ✅ Implemented |
| 20-year parameter optimization + econometric proofs | ✅ Implemented |
| Walk-forward out-of-sample track record | ✅ Implemented |
| Landing site with interactive charts | ✅ Implemented |
| Telegram tiered delivery (public vs Pro) | ✅ Implemented |
| Cashfree payment flow (orders, signed webhooks, invite links) | ✅ Implemented |
| Security hardening (rate limits, CORS, headers, signature verification) | ✅ Implemented |
| GitHub Actions weekly automation | ✅ Implemented |
| Unit tests (60, all passing) | ✅ Passing |
| Live payments + Telegram delivery configured | ⏳ Remaining (launch steps) |

### Latest track record (as of 2026-07-31)
- **362** simulated trades over the last 5 years (walk-forward, out-of-sample)
- **41.1%** win rate · **+140.5%** cumulative return · **+0.39%** avg return/trade
- Latest signal: **1 ACTIVE trade** (Atlantic Chlorophyll → Tuna, HIGH confidence, SHORT 12.84 / SL 13.48 / TP 11.81)

> Simulated results for educational purposes only — they do not reflect real execution, slippage, or costs.

---

## The Signal Pairs

| # | Ocean Indicator | Commodity | Optimal Lag | Max \|r\| |
|---|-----------------|-----------|:----------:|:-------:|
| 1 | Pacific SST Anomaly (ENSO) | Copper Futures | 50 days | 0.38 |
| 2 | Atlantic Chlorophyll | Tuna Price | 30 days | 0.99 |
| 3 | GoM Chemical Plume | Crude Oil Futures | 110 days | 0.14* |

\* Not continuously tradeable — oil seeps act as discrete event catalysts (cointegration unproven on a daily-returns basis).

**Proven causalities** (Granger, p < 0.05): Pacific SST → Copper (50-day lead) and Atlantic Chlorophyll → Tuna (30-day lead). El Niño threshold events (> +1.0°C anomaly) show a +9.16% average 12-week forward return on Copper in event studies.

---

## What Has Been Accomplished

### 1. Quant research & validation
- **20-year dataset (2006–2026)**: 7,450+ daily observations across 3 ocean/commodity pairs.
- **Multicore parameter optimization** (`quant_optimizer.py`) sweeping smoothing windows and lag offsets to maximize absolute correlation.
- **Institutional proofs** (`quant_econometrics.py`): Dickey-Fuller stationarity tests and VAR/Granger causality for every pair.
- **Event studies**: threshold-based forward-return analysis (e.g., El Niño events).
- Full research write-up in [`walkthrough.md`](walkthrough.md).

### 2. Signal engine (`deepstream/signal_engine.py`)
- Computes lagged Pearson correlation between ocean indicator and commodity price.
- Grades confidence by absolute |r|: **HIGH ≥ 0.70, MEDIUM ≥ 0.40, LOW ≥ 0.20, NOISE**.
- Only HIGH / MEDIUM emit tradeable setups with **entry / stop (5%) / target (8%)**.
- Fully config-driven — thresholds, risk, and asset definitions live in `deepstream/config.py`.

### 3. Honest track record (`deepstream/track_record.py`)
- Replays the engine historically using **only data available at each signal date** — no lookahead bias.
- Conservative outcome resolution (closing prices only, never intraday).
- Published live on the site as `track_record.json` with full methodology disclosure.

### 4. Landing site (`signal_site/`)
- Premium landing page with interactive price/ocean charts, signal cards, and equity curve.
- Static deployment target for Netlify (`netlify.toml`), legal pages (terms, privacy, refunds, contact), and `success.html` payment return page.
- Machine-readable endpoints: `/latest_signal.json`, `/track_record.json`, `/chart_data.json`.

### 5. Telegram delivery (`deepstream/telegram.py`)
- **Public channel**: weekly summary — direction + confidence grades only, never levels.
- **Pro channel**: full setups with entry / stop / target.
- Either channel may be unset; delivery still succeeds.

### 6. Payments — Cashfree (`deepstream/payments.py` + `netlify/functions/`)
- `POST /api/create-order` → Cashfree order + `payment_session_id` for the hosted checkout.
- **Signed webhooks** (`x-webhook-signature`, HMAC-SHA256) verified before any action; `ORDER_PAID` is re-checked against the Cashfree API (amount + currency) before granting.
- On verified payment the bot mints a **single-use, 30-day Telegram invite link** to the private Pro channel, keyed by `order_id`.
- Refunds / failed / cancelled orders revoke the link.
- Success page polls `/api/access?order_id=...` until the invite appears.
- **Two identical backends**: the local Python dev server and Netlify Functions (state in Netlify Blobs) mirror the same logic.

### 7. Security hardening
- Per-IP rate limiting, request body caps, server-side email/order-id validation.
- CORS restricted to the configured site origin; security headers on every response.
- Never exposes the Cashfree client secret to the browser.

### 8. Automation & CI (`run_weekly.sh`, `.github/workflows/weekly.yml`)
- GitHub Actions cron every **Monday 05:00 UTC** (or manual dispatch): install → run tests (gate) → generate signals + track record → deliver to Telegram → commit refreshed assets back to the repo → Netlify redeploys.
- `./run_weekly.sh` for local runs (with `--skip-pipeline` for fast offline runs).

### 9. Tooling & tests
- `verify_telegram.py` — one-command health check of bot token, Pro-channel admin status, and invite-link permission (with `--test-invite` end-to-end proof).
- `run_sandbox_e2e.py` — Cashfree sandbox end-to-end harness (`preflight` / `create` / `webhook` / `check` / `all`).
- **60 unit tests** across signal engine, payments, server security, Telegram, and verification — all passing.

---

## What's Left (Launch Steps)

The code is complete; the remaining work is **account/credential setup and go-live validation**:

### Go-live checklist
- [ ] **Cashfree account** — sandbox keys work immediately; production requires KYC + ~24–48h activation.
- [ ] **`.env` configured** — copy `.env.example` → `.env` and fill in all values (bot token, channel IDs, Cashfree keys, webhook secret, site URL). Set the same vars as Netlify environment variables.
- [ ] **Private Pro Telegram channel** — create it, add the bot as admin with **"Invite users via link"** permission, set `DEEPSTREAM_PRO_CHANNEL_ID`.
- [ ] **Webhook URL registered** in the Cashfree dashboard for `ORDER_PAID`, `ORDER_FAILED`, `ORDER_CANCELLED`, `REFUND_STATUS` → `https://<your-domain>/webhooks/cashfree`.
- [ ] **Domain whitelisted** in the Cashfree dashboard (production).
- [ ] **`CASHFREE_SITE_URL`** points at the deployed site.
- [ ] **Sandbox end-to-end test** — `python verify_telegram.py --test-invite` then `python run_sandbox_e2e.py all` (test card `4111 1111 1111 1111`, CVV `123`, OTP `111000`, or UPI `testsuccess@gocash`) confirms order → webhook → invite → access.
- [ ] **Verify the webhook signature variant** Cashfree actually delivers (body-only vs timestamp+body) against a real dashboard test event — the code accepts both, but confirm before going live.
- [ ] **Production switch** — set `CASHFREE_ENV=production` after KYC activation.
- [ ] **First weekly run** — `./run_weekly.sh` (or the GitHub Actions schedule) and confirm delivery to both channels.

### Optional future work
- **Billing note:** the Pro tier is billed in **INR (₹2,499/mo)** as a monthly order — each successful payment grants 30 days via a fresh invite link. Since billing is INR, Cashfree's native auto-recurring subscriptions (UPI AutoPay / eNACH) are available as a future upgrade from the current monthly-order flow.
- Add edge-level (CDN/WAF) rate limiting in front of the Netlify Functions (in-memory limiter is best-effort per warm instance).
- Expand beyond the 3 monitored pairs as new ocean datasets become available.

---

## Architecture

```
deepstream/
  config.py            # asset pairs, thresholds, risk, delivery settings
  logging_setup.py     # structured rotating-file logging
  signal_engine.py     # lagged correlation → trade setups + confidence grades
  track_record.py      # walk-forward, out-of-sample performance replay
  telegram.py          # tiered Telegram delivery (public summary / Pro report)
  payments.py          # Cashfree orders, signed webhooks, invite-link fulfillment
  chart_data.py        # time-series + equity-curve payload for the site
  server.py            # local dev backend (landing site + JSON endpoints)
  cli.py / __main__.py # `python -m deepstream {generate,track,run}`

netlify/
  functions/           # production payment backend (mirrors deepstream/payments.py)
    create-order.mjs   # POST /api/create-order
    cashfree-webhook.mjs  # POST /webhooks/cashfree
    access.mjs         # GET /api/access?order_id=
    payments-config.mjs   # GET /api/payments_config
    _shared/cashfree.mjs  # shared API / signature / blob-storage helpers

signal_site/           # landing page (static, published by Netlify)
tests/                 # 60 unit tests
fetch_data.py          # pulls ocean + price data into data/
quant_optimizer.py     # 20-year multicore parameter optimization
quant_econometrics.py  # stationarity + Granger causality proofs
run_backtests.py       # historical backtest engine
run_weekly.sh          # weekly pipeline wrapper
verify_telegram.py     # Telegram setup health check
run_sandbox_e2e.py     # Cashfree sandbox end-to-end harness
plan.md                # monetization plan & go-live details
walkthrough.md         # full research & implementation report
```

**Payment flow:** landing page → `POST /api/create-order` → Cashfree hosted checkout → signed webhook → verify signature → re-check order against Cashfree API (PAID, amount, currency) → mint single-use Pro-channel invite link → `success.html` polls `/api/access` → customer gets the link. Refunds/failures revoke it.

---

## Setup

### Prerequisites
- Python 3.10+ (developed against 3.12) with `pip`
- Node.js 18+ only needed for Netlify Functions (`npm install` in `netlify/functions` — dependency: `@netlify/blobs`)

### Installation

```bash
pip install -r requirements.txt
cp .env.example .env     # then fill in your values (see below)
```

### Environment variables (`.env`)

| Variable | Purpose |
|----------|---------|
| `DEEPSTREAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `DEEPSTREAM_CHANNEL_ID` | Public channel for free weekly summaries (optional) |
| `DEEPSTREAM_PRO_CHANNEL_ID` | Private Pro channel — bot must be admin with invite-link permission |
| `CASHFREE_CLIENT_ID` / `CASHFREE_CLIENT_SECRET` | Cashfree merchant API keys |
| `CASHFREE_ENV` | `sandbox` (default) or `production` |
| `CASHFREE_API_VERSION` | API version, default `2023-08-01` |
| `CASHFREE_WEBHOOK_SECRET` | Secret from the Cashfree webhook config |
| `CASHFREE_ORDER_AMOUNT` / `CASHFREE_ORDER_CURRENCY` | Price per Pro month (default `2499` / `INR`) |
| `CASHFREE_SITE_URL` | Deployed site URL (used as the checkout return URL) |

---

## Usage

### CLI

```bash
python -m deepstream generate              # emit latest_signal.json
python -m deepstream track                 # emit track_record.json
python -m deepstream run                   # generate + track + refresh site assets
python -m deepstream run --skip-pipeline   # fast offline run (uses existing data)
python -m deepstream.telegram              # deliver weekly report to Telegram
python -m deepstream.server                # serve the site + APIs on :8080
```

### Weekly run

```bash
./run_weekly.sh                 # full pipeline (fetch + optimize + backtest + track)
./run_weekly.sh --skip-pipeline # offline-safe, uses existing data
```

Or let GitHub Actions do it automatically every Monday (`.github/workflows/weekly.yml`).

### Testing

```bash
python -m unittest discover -s tests   # 60 tests
```

### Pre-flight checks

```bash
python verify_telegram.py               # bot token + channel admin + invite permission
python verify_telegram.py --test-invite # plus a real mint/revoke round trip
python run_sandbox_e2e.py preflight     # payment env + target-server readiness
```

---

## Deployment

- **Site**: static (`signal_site/`) published by Netlify (`netlify.toml`).
- **Payment backend**: Netlify Functions (`netlify/functions/`) with order state in **Netlify Blobs** — set the Cashfree + Telegram vars as Netlify environment variables.
- **Weekly automation**: GitHub Actions on schedule or manual dispatch; refreshed signal/track/chart assets are committed back automatically, triggering a Netlify redeploy.
- **Local dev**: `python -m deepstream.server` serves the same site and API routes (state in `data/subscriptions.json`).

---

## Documentation

- [`plan.md`](plan.md) — monetization strategy, revenue model, delivery split, go-live checklist.
- [`walkthrough.md`](walkthrough.md) — the definitive research report: concepts, 20-year optimization results, econometric proofs, event studies, and dashboard features.
- [`deepstream/config.py`](deepstream/config.py) — every threshold and risk parameter, auditable in one place.
