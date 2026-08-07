# Deepstream — User Guide

How Deepstream works, what you get at each tier, and how to receive and read
your weekly signals.

---

## What is Deepstream?

Deepstream converts **physical ocean data** — sea-surface temperature
anomalies, chlorophyll concentration, and subsea chemical plumes — into
**weekly commodity trade setups** for Copper, Tuna, and Crude Oil.

Every setup is produced by a **walk-forward engine**: it uses only the data
available at publication time, so nothing is retrofitted to history. The full
trade-by-trade track record is published openly on the site.

## The signal pairs

| # | Ocean indicator | Commodity | Optimal lead |
|---|-----------------|-----------|:------------:|
| 1 | Pacific SST anomaly (ENSO) | Copper futures | 50 days |
| 2 | Atlantic chlorophyll | Tuna price | 30 days |
| 3 | Gulf of Mexico chemical plume | Crude oil futures | 110 days (event-driven) |

Causality for pairs 1 and 2 is Granger-proven at p < 0.05 over 20 years of
data. Pair 3 is treated as a discrete event catalyst rather than a continuous
signal — and is traded accordingly, or not at all.

## Tiers

| Tier | Price | What you get |
|------|-------|--------------|
| **Free** | ₹0 | Weekly position summary + confidence grades on the public Telegram channel. You see *which* signal is live and how strong it is — never the levels. |
| **Pro** | ₹2,499/month | Full setups with **entry, stop loss, and take profit**, confidence and lead time, the complete walk-forward track record, and methodology updates — delivered to a private Telegram channel. |

## How to subscribe (Pro)

1. On the landing page, open **Pricing → Subscribe**.
2. Enter your **email** and **phone** (Cashfree requires a valid 10–15 digit
   number to create the order).
3. You are redirected to Cashfree's secure checkout. Pay with any card or UPI.
4. After payment you land on the success page, which shows your **private
   Telegram invite link** within a few seconds.
5. Click the link to join the Pro channel. It is **single-use** and valid for
   **30 days**. Renewing is a fresh payment that mints a fresh invite.

> The invite link is one-use: if you join with a second Telegram account, the
> link will not work for that account. Renewals and re-issues are handled by
> emailing billing@deepstream.example.

## Reading a signal

A Pro setup looks like this:

```
[HIGH] Atlantic Chlorophyll → Tuna Price
  [SHORT] Entry 12.84 | SL 13.48 | TP 11.81
  r = -0.775 | lead 30d | HIGH confidence
```

- **Direction** — LONG (buy) or SHORT (sell) the instrument.
- **Entry** — the level at which the setup activates.
- **SL** — stop loss: where the trade is abandoned if wrong (5% from entry).
- **TP** — take profit: where the trade is closed if right (8% from entry).
- **r** — the Pearson correlation behind the signal (absolute value = strength).
- **Lead** — how many days before price action the ocean signal fired.
- **Confidence** — HIGH (|r| ≥ 0.70), MEDIUM (≥ 0.40), LOW (≥ 0.20), NOISE (< 0.20).
  Only HIGH and MEDIUM produce tradeable setups.

## What "walk-forward, out-of-sample" means

Most backtests optimize over the full dataset and then "replay" it — which
leaks future information. Deepstream instead replays each historical date
using **only data available up to that date**, generating the exact setup a
subscriber would have received, then measuring the actual forward outcome
(closed at stop or target, or marked to market at 60 days). The result is a
record that shows what the product *actually* did, losses included.

## Frequently asked

**Is this financial advice?** No. Deepstream is a quantitative research
service. Signals are informational and educational; you are solely
responsible for your trading decisions.

**What if there are no high-confidence signals?** We publish "no trade".
Standing aside is a position — we never fabricate a setup.

**How do I cancel?** Pro is a monthly order, not a subscription. Simply do
not renew. There is no lock-in and no auto-charge.

**Do you refund?** See the refund policy on the site. Refunds revoke the
active invite link.

## Getting help

- Contact page on the site, or email support at
  **support@deepstream.example**.
- Report issues with a screenshot and the signal date — it helps us trace
  the exact data snapshot.
