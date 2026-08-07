# AI Prompts Archive

The prompts used to build and maintain Deepstream, preserved so future
sessions can be re-run with consistent context. Treat these as living
documents — update them when the product changes.

## 1. System scaffolding prompt

> Build a config-driven Python signal platform that converts oceanographic
> data (NOAA sea-surface temperature, chlorophyll, chemical plumes) into
> weekly commodity trade setups (Copper, Tuna, Crude Oil). Requirements:
> - Walk-forward, out-of-sample track record (no lookahead bias) published
>   as JSON for the landing site.
> - Confidence grading by absolute Pearson r (HIGH ≥ 0.70, MEDIUM ≥ 0.40,
>   LOW ≥ 0.20, else NOISE); only HIGH/MEDIUM emit tradeable setups with
>   5% stop / 8% target.
> - All thresholds and asset definitions in one `config.py`.
> - Tiered Telegram delivery: public summary without levels, Pro report
>   with entry/stop/target.
> - CLI: `python -m deepstream {generate,track,run}`.
> - Unit tests for the engine.

## 2. Payments integration prompt

> Add a Cashfree Payment Gateway flow: the landing page posts an email+phone
> to `POST /api/create-order`, the backend creates a ₹2,499/month order and
> returns a `payment_session_id` for the hosted checkout. Verify HMAC-SHA256
> signed webhooks at `POST /webhooks/cashfree`; on verified ORDER_PAID
> (re-checked against the Cashfree API for amount and currency) mint a
> single-use 30-day Telegram invite link to a private Pro channel keyed by
> order_id. Revoke on refund/failure. success.html polls
> `GET /api/access?order_id=`. Mirror the logic as Netlify Functions with
> state in Netlify Blobs. Harden: per-IP rate limits, body caps, server-side
> email/order-id/phone validation, CORS restricted to the site origin,
> security headers. Keep the client secret server-side only.

## 3. UI/UX polish prompt (this pass)

> Polish the dark operations console: consistent spacing and typography,
> visible keyboard focus, reduced-motion support, a mobile off-canvas drawer
> with hamburger toggle, loading spinners for chart recalculation, an empty
> state when the dataset is missing, transient toast feedback, hover states
> on tables and cards, and class-based styling instead of inline styles.
> Keep the existing design language intact.

## 4. Marketing automation prompt (this pass)

> Add inbound marketing systems with minimal manual effort: SEO metadata,
> Open Graph + JSON-LD structured data, robots.txt + sitemap, a newsletter
> signup via Netlify Forms, a changelog page rendered from JSON, and a
> data-driven content generator that produces LinkedIn/X posts, email
> campaigns, blog drafts, and changelog entries from the published signal
> and track-record JSON — never inventing numbers. No cold outreach.

## Maintenance rules
- Keep prompts in this file in sync with the actual architecture (the
  `deepstream/` layout and `netlify/functions/` mirror).
- When a new subsystem lands, add its build prompt here for reproducibility.
