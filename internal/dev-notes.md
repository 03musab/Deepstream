# Deepstream — Development Notes

Internal architecture notes for maintainers. Public-facing docs live in
[`docs/`](../docs/) and the landing site in [`signal_site/`](../signal_site/).

## Architecture at a glance

```
scripts/            # research + ops scripts (data fetch, optimization, verification)
deepstream/         # Python package — the signal platform (backend)
  config.py         #   all thresholds, assets, paths (single source of truth)
  validation.py     #   server-side input validation (email/order/phone)
  middleware.py     #   rate limiting + security headers
  server.py         #   HTTP routes/handlers (local dev backend)
  signal_engine.py  #   lagged correlation -> trade setups + confidence grades
  track_record.py   #   walk-forward, out-of-sample performance replay
  telegram.py       #   tiered Telegram delivery (public summary / Pro report)
  payments.py       #   Cashfree orders, signed webhooks, invite-link fulfillment
  chart_data.py     #   time-series + equity payload for the site
netlify/            # production payment backend (mirrors deepstream/payments.py)
signal_site/        # deployed landing site (Netlify publish dir)
docs/               # client deliverables (research report, user guide, API ref)
internal/           # workspace (dev notes, prompts, marketing)
tests/              # unit tests (python -m unittest discover -s tests)
```

## The two backends (keep them in sync!)

The **Python server** (`python -m deepstream.server`) and the **Netlify
Functions** (`netlify/functions/`) implement the *same* payment flow:

| Concern | Python | Netlify |
|---------|--------|---------|
| Create order | `deepstream/payments.py` | `functions/create-order.mjs` |
| Webhook verify | `payments.verify_webhook_signature` | `_shared/cashfree.mjs` |
| Grant/revoke | `payments.SubscriptionStore` | `_shared/cashfree.mjs` (Blobs) |
| Validation | `deepstream/validation.py` | `_shared/cashfree.mjs` |
| Config/security | `deepstream/config.py` + `middleware.py` | `_shared/cashfree.mjs` + `signal_site/_headers` |

When you change a rule in one (e.g. a regex, a status set, a TTL), change it
in the other. The unit tests pin the Python side; the sandbox E2E harness
(`scripts/run_sandbox_e2e.py`) exercises the live flow.

## Conventions

- **Config-driven behaviour**: any tunable (thresholds, risk, paths, env var
  names) lives in `deepstream/config.py`. Never hardcode a second copy.
- **Relative paths in scripts**: `scripts/*.py` assume the **repo root** as
  CWD (that is how `run_weekly.sh` and the CLI invoke them).
- **No secrets in the repo**: `.env` is gitignored. `.env.example` documents
  every variable. `CASHFREE_CLIENT_SECRET` never reaches the browser — the
  Functions/Python server are the only holders.
- **Honesty is the product**: track record and signal JSONs are generated
  walk-forward; marketing copy (`internal/marketing/content-generator.py`)
  only cites published numbers.
- **Naming**: snake_case Python, kebab-case assets, `ds_`-prefixed order ids,
  `test_<n>` parameter keys. Confidence grades are uppercase enums
  (HIGH/MEDIUM/LOW/NOISE).

## Weekly pipeline

`run_weekly.sh` (or GitHub Actions `weekly.yml`):

1. `python -m deepstream run` → fetch → optimize → backtest → generate
   `latest_signal.json` + `track_record.json` → refresh `signal_site/` assets.
2. `python -m deepstream.telegram` → public summary + Pro report.
3. CI commits the refreshed assets; Netlify redeploys the site.

Optional after a refresh: `python internal/marketing/content-generator.py all`
to produce the week's marketing copy and changelog entry.

## Gotchas

- The GitHub Action's `git add` includes `plots/` and `data/` — keep those
  tracked; do not gitignore them or the commit step fails.
- `data-store.js` is generated (`scripts/convert_csv_to_js.py`) but committed
  because `index.html` (operations console) needs it at rest.
- Cashfree sandbox can answer `POST /pg/orders` with HTTP 500 while the order
  was actually created — both backends recover via a `GET` (see
  `create_cashfree_order`). Don't "fix" that by removing the recovery.
- Webhook signatures: accept body-only *and* timestamp+body variants until
  the deployed Cashfree account's exact scheme is confirmed.
