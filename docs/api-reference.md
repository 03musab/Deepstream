# Deepstream — API Reference

Machine-readable endpoints for the landing site and the payment flow. The
same endpoints are served by the local Python dev server
(`python -m deepstream.server`, port 8080) and the Netlify Functions in
production.

---

## Public data endpoints (no auth)

### `GET /latest_signal.json`

The current weekly signal set.

```json
{
  "generated_at": "2026-08-03T08:20:34Z",
  "signals": [
    {
      "pair_id": 2,
      "pair": "Atlantic Chlorophyll → Tuna Price",
      "direction": "SHORT",
      "confidence": "HIGH",
      "pearson_r": -0.7754,
      "lag_days": 30,
      "entry": 12.84,
      "stop_loss": 13.48,
      "take_profit": 11.81,
      "status": "ACTIVE"
    }
  ],
  "summary": { "total": 3, "active": 1, "high_confidence": 1, "medium_confidence": 0 }
}
```

`status` is one of `ACTIVE | NO_TRADE | NO_DATA | INSUFFICIENT_DATA`.

### `GET /track_record.json`

The walk-forward performance record: methodology, aggregate statistics, and
a trade-by-trade log.

### `GET /chart_data.json`

Time-series per pair (price + ocean indicator, ~520 points) plus the
cumulative equity curve for the site charts.

---

## Payment endpoints

### `POST /api/create-order`

Creates a Cashfree order for one month of Pro access.

**Request**

```json
{
  "customer_email": "you@example.com",
  "customer_phone": "919876543210"
}
```

`customer_phone` must be 10–15 digits (formatting characters are stripped).
The email must pass server-side validation.

**Response (200)**

```json
{
  "order_id": "ds_0123456789abcdef",
  "payment_session_id": "session_...",
  "order_status": "ACTIVE"
}
```

Hand `payment_session_id` to the Cashfree JS SDK to render the hosted
checkout. Errors return `400` (validation), `413` (body too large),
`429` (rate limited), or `502` (provider failure — `detail` carries the
provider's real message).

### `POST /webhooks/cashfree`

Cashfree's signed webhook endpoint. **Every request must carry a valid
`x-webhook-signature` (HMAC-SHA256 over the raw body, optionally prefixed
with `x-webhook-timestamp`); otherwise it is rejected with `401`.**

Handled events: `ORDER_PAID` (grants access after re-checking the order via
the Cashfree API), `ORDER_FAILED` / `ORDER_CANCELLED` (marks failed),
`REFUND_STATUS` variants (revokes access). Responses: `200` on success,
`500` when processing failed (Cashfree retries).

### `GET /api/access?order_id=ds_...`

Polled by `success.html` after payment.

```json
{ "status": "granted", "invite_link": "https://t.me/+...", "expires_at": "2026-09-02T..." }
```

`status` is `granted | pending | revoked`. `order_id` must match
`ds_[0-9a-f]{16}`.

### `GET /api/payments_config`

Public-safe SDK configuration for the checkout UI:

```json
{
  "configured": true,
  "mode": "sandbox",
  "amount": 2499,
  "currency": "INR"
}
```

---

## Security model

- **Client secret never reaches the browser.** Only the Python server / the
  Netlify Functions hold `CASHFREE_CLIENT_SECRET` and the Telegram bot token.
- **Webhooks are signed and re-verified** against the Cashfree API before any
  grant (order must be `PAID`, amount and currency must match).
- **Server-side validation** on every input (see `deepstream/validation.py`
  and `netlify/functions/_shared/cashfree.mjs`).
- **Rate limits** per IP on order creation, webhooks, and access polling.
- **CORS** is restricted to the configured site origin; security headers are
  applied to every response.
- **Invite links are single-use** and valid 30 days; refunds/failures revoke
  them.

## Local development

```bash
set -a; source .env; set +a
python -m deepstream.server     # serves site + APIs on :8080
```

Verify the flow end-to-end in the Cashfree sandbox:

```bash
python scripts/verify_telegram.py            # bot + channel + invite permission
python scripts/run_sandbox_e2e.py all        # create → pay → webhook → access
```
