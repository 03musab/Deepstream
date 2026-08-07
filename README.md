<div align="center">

# Deepstream

**The ocean moves commodities. We trade that signal.**

Ocean-data commodity signal platform — converts sea-surface temperature,
chlorophyll, and chemical-plume observations into statistically validated
weekly commodity trade setups (Copper · Tuna · Crude Oil), delivered via
Telegram and monetized through a paid Pro tier.

![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-72%20passing-3dd68c)
![Deploy](https://img.shields.io/badge/deploy-Netlify-00C7B7?logo=netlify&logoColor=white)

</div>

---

## Overview

Deepstream turns physical oceanography into a trading edge. Instead of
fitting models to price history, it tracks the *physical systems that
precede markets*:

- **El Niño / La Niña** (Pacific SST anomalies) disrupt rainfall around South
  American copper mines → **Copper futures**, ~50-day lead.
- **Chlorophyll collapses** (Atlantic) signal food-chain disruption →
  **Tuna prices**, ~30-day lead.
- **Subsea chemical plumes** (Gulf of Mexico) flag infrastructure stress →
  **Crude oil**, traded as discrete event catalysts.

The product is differentiated by **honest methodology**: signals are produced
walk-forward (no lookahead bias), Granger-causality tested over 20 years of
history, and an out-of-sample track record is published trade-by-trade on the
landing site.

> **Simulated results for educational purposes only** — they do not reflect
> real execution, slippage, or costs.

## Features

| Area | Status |
|------|--------|
| Signal engine — 3 ocean → commodity pairs | ✅ |
| 20-year parameter optimization + econometric proofs | ✅ |
| Walk-forward, out-of-sample track record | ✅ |
| Landing site with interactive charts & machine-readable JSON | ✅ |
| Telegram tiered delivery (public summary vs Pro report) | ✅ |
| Daily Pro-channel position updates | ✅ |
| Cashfree payment flow (orders, signed webhooks, invite links) | ✅ |
| Security hardening (rate limits, CORS, headers, signature verification) | ✅ |
| GitHub Actions automation (weekly + daily) | ✅ |
| Marketing automation (SEO, changelog, newsletter, content generator) | ✅ |
| Unit tests — **72, all passing** | ✅ |

### Latest track record (2026-08-03)

- **362** simulated trades over the last 5 years (walk-forward, out-of-sample)
- **41.1%** win rate · **+140.5%** cumulative return · **+0.39%** avg return/trade
- Latest signal: **1 ACTIVE trade** — Atlantic Chlorophyll → Tuna, HIGH
  confidence, SHORT 12.84 / SL 13.48 / TP 11.81

## Tech stack

- **Backend:** Python 3.12 (stdlib-only HTTP server + NumPy/Pandas/Scipy
  analysis), config-driven `deepstream` package.
- **Production backend:** Netlify Functions (Node 18+) + Netlify Blobs,
  mirroring the Python payment logic.
- **Frontend:** Vanilla JS + Chart.js, two surfaces — the deployed landing
  site (`signal_site/`) and the operations console (`index.html`).
- **Data:** NOAA CPC (SST indices), Yahoo Finance (futures), simulated
  chlorophyll/plume series where no open API exists.
- **Payments:** Cashfree Payment Gateway (₹2,499/month, INR).
- **Delivery:** Telegram Bot API (public + private Pro channel, single-use
  invite links).
- **CI/CD:** GitHub Actions (weekly + daily cron) → Netlify static deploy.

## Repository structure

```
Deepstream/
├── deepstream/          # Python package — signal platform (backend)
│   ├── config.py        #   every threshold, asset, path (single source of truth)
│   ├── validation.py    #   server-side input validation
│   ├── middleware.py    #   rate limiting + security headers
│   ├── server.py        #   HTTP routes/handlers (local dev backend)
│   ├── signal_engine.py #   lagged correlation → trade setups + grades
│   ├── track_record.py  #   walk-forward out-of-sample replay
│   ├── telegram.py      #   tiered Telegram delivery
│   ├── payments.py      #   Cashfree orders, signed webhooks, invite fulfillment
│   └── chart_data.py    #   chart payloads for the site
├── scripts/             # research & ops scripts (fetch, optimize, verify, e2e)
├── netlify/             # production payment backend (functions/)
│   └── functions/       #   create-order · cashfree-webhook · access · payments-config
├── signal_site/         # deployed landing site (Netlify publish dir)
├── docs/                # client deliverables (research report, user guide, API ref)
├── internal/            # workspace (dev notes, AI prompts, marketing automation)
├── tests/               # 72 unit tests
├── data/                # processed ocean + price datasets
├── plots/               # diagnostic plots (tracked — CI pushes them)
├── index.html           # operations console (admin UI)
├── data-store.js        # compiled browser dataset (generated)
├── run_weekly.sh        # weekly pipeline wrapper
└── netlify.toml         # publish dir, functions dir, redirects
```

## Installation

**Prerequisites**

- Python 3.10+ (developed against 3.12) with `pip`
- Node.js 18+ only for the Netlify Functions (`npm install`)

```bash
git clone https://github.com/03musab/Deepstream.git
cd Deepstream

pip install -r requirements.txt
cp .env.example .env       # then fill in your values (see below)
```

## Environment variables

All variables are documented in `.env.example`:

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

The same variables must be set as **Netlify environment variables** for the
production Functions.

## Running the frontend

**Landing site** (what customers see) — served by the local backend, or
directly from `signal_site/`:

```bash
python -m deepstream.server          # serves signal_site/ + APIs on :8080
# open http://localhost:8080
```

**Operations console** (admin/demo UI) — a standalone static page:

```bash
python -m http.server 8000           # from the repo root
# open http://localhost:8000/index.html
```

## Running the backend

```bash
python -m deepstream generate              # emit latest_signal.json
python -m deepstream track                 # emit track_record.json
python -m deepstream run                   # generate + track + refresh site assets
python -m deepstream run --skip-pipeline   # fast offline run (uses existing data)
python -m deepstream.telegram              # deliver weekly report to Telegram
python -m deepstream daily                 # daily Pro-channel position update
python -m deepstream daily --no-fetch      # daily update without a price refresh
python -m deepstream.server                # serve the site + APIs on :8080
```

### Weekly run

```bash
./run_weekly.sh                 # full pipeline (fetch + optimize + backtest + track)
./run_weekly.sh --skip-pipeline # offline-safe, uses existing data
```

Or let GitHub Actions do it automatically every Monday
(`.github/workflows/weekly.yml`).

### Daily Pro updates

`python -m deepstream daily` fetches fresh commodity prices (with `--no-sim`,
so a failed fetch never replaces real data with simulated series), recomputes
the signals, and posts the current setups (entry · stop · target) to the
**private Pro channel**. The weekly site assets and track record are
untouched. GitHub Actions runs this every day at 06:00 UTC
(`.github/workflows/daily.yml`); use `--no-fetch` to skip the price refresh
for a fast offline run.

## Build process

There is no compile step for the site (static assets). Generated artifacts:

```bash
python scripts/fetch_data.py             # pulls ocean + price data into data/
python scripts/quant_optimizer.py        # multicore grid-search → optimized_parameters.json
python scripts/run_backtests.py          # historical backtest engine + plots/
python scripts/convert_csv_to_js.py      # data/*.csv → data-store.js (browser dataset)
```

`python -m deepstream run` chains the pipeline, then copies the refreshed
`latest_signal.json`, `track_record.json`, and `chart_data.json` into
`signal_site/` for deployment.

## Marketing automation

Inbound-only systems, no cold outreach:

- **Weekly content generator** — `python internal/marketing/content-generator.py all`
  produces LinkedIn/X posts, a subscriber email, a blog draft, a feature
  announcement, and appends a changelog entry — all from the *published*
  signal/track-record numbers (never invented).
- **Landing page SEO** — Open Graph, Twitter cards, JSON-LD structured data
  (Organization, WebSite, FAQPage), `robots.txt`, `sitemap.xml`.
- **Newsletter / lead capture** — Netlify Forms signup in the site footer.
- **Changelog** — `signal_site/changelog.html` rendered from
  `signal_site/changelog.json`.
- **Templates & frameworks** — `internal/marketing/`: email campaigns, social
  cadence, referral program.

## Testing

```bash
python -m unittest discover -s tests     # 72 tests

# Pre-flight / end-to-end checks
python scripts/verify_telegram.py               # bot token + channel admin + invite permission
python scripts/verify_telegram.py --test-invite # plus a real mint/revoke round trip
python scripts/run_sandbox_e2e.py preflight     # payment env + target-server readiness
python scripts/run_sandbox_e2e.py all           # create → pay → webhook → access (sandbox)
```

## Deployment

- **Site:** static (`signal_site/`) published by Netlify (`netlify.toml`).
- **Payment backend:** Netlify Functions (`netlify/functions/`) with order
  state in Netlify Blobs — set the Cashfree + Telegram vars as Netlify
  environment variables. Register the webhook URL
  `https://<your-domain>/webhooks/cashfree` for `ORDER_PAID`,
  `ORDER_FAILED`, `ORDER_CANCELLED`, `REFUND_STATUS` in the Cashfree
  dashboard.
- **Weekly automation:** GitHub Actions on schedule or manual dispatch;
  refreshed assets are committed back, triggering a Netlify redeploy.
- **Daily Pro updates:** `daily.yml` runs `python -m deepstream daily` every
  day at 06:00 UTC — fresh prices, recomputed signals, delivered to the
  private Pro channel. No assets are committed.

### Go-live checklist

- [ ] `.env` configured with real credentials; same vars set on Netlify
- [ ] Cashfree production KYC approved; `CASHFREE_ENV=production`
- [ ] Webhook URL + secret registered; domain whitelisted
- [ ] Private Pro channel created; bot admin with "Invite users via link"
- [ ] `python scripts/run_sandbox_e2e.py all` passes end-to-end
- [ ] Confirm which webhook signature variant Cashfree delivers
      (body-only vs timestamp+body — the code accepts both)

## Future roadmap

- **Recurring billing** — migrate monthly orders to Cashfree auto-recurring
  subscriptions (UPI AutoPay / eNACH), since billing is INR-native.
- **Referral program** — implement the framework in
  `internal/marketing/referral-program.md` (unique links + credit ledger).
- **More pairs** — expand beyond the 3 monitored markets as new ocean
  datasets become available.
- **Edge rate limiting** — CDN/WAF-level limits in front of the Functions
  (the in-memory limiter is best-effort per warm instance).
- **Blog** — publish generated article drafts to a `signal_site/blog/`
  index for organic search.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Cashfree credentials are not configured` | Set `CASHFREE_CLIENT_ID` / `CASHFREE_CLIENT_SECRET` in the server's env, then restart/redeploy. |
| `createChatInviteLink failed: not enough rights` | The bot is not admin of the Pro channel, or lacks "Invite users via link". Run `python scripts/verify_telegram.py`. |
| Webhook returns `401 invalid signature` | `CASHFREE_WEBHOOK_SECRET` mismatch, or the dashboard uses a different signature scheme. The code accepts body-only and timestamp+body variants. |
| `create-order` returns `502` with a provider detail | Read the `detail`/`code` field — it is Cashfree's real reason (e.g. sandbox account rejecting the order). |
| Charts empty on the operations console | Rebuild `data-store.js`: `python scripts/convert_csv_to_js.py`. |
| Track record shows `0 trades` | `data/*.csv` missing — run `python scripts/fetch_data.py` first. |
| `Order not yet seen` on the success page | The webhook hasn't processed yet (polls every 2s, up to 60s), or the webhook URL/secret is misconfigured. |

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/your-change`).
3. Make changes — keep behaviour config-driven (`deepstream/config.py`),
   keep the Python and Netlify backends in sync, and never commit secrets.
4. Add/update unit tests under `tests/` and run
   `python -m unittest discover -s tests`.
5. Open a pull request with a clear description.

See [`internal/dev-notes.md`](internal/dev-notes.md) for architecture and
conventions, and [`docs/`](docs/) for the research report, user guide, and
API reference.

## License

Proprietary — all rights reserved. The research report and track record are
published for transparency; the product itself is not open source.
