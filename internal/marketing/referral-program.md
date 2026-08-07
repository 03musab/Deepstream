# Referral Program Framework

Goal: turn Pro subscribers into the acquisition channel. No cold outreach —
referrals are warm by definition.

## Mechanics

| Element | Default | Rationale |
|---------|---------|-----------|
| Reward | 1 free Pro month (₹2,499) per referred paying subscriber | Cash-equivalent, no payment-rail complexity |
| Cap | 3 credits/month | Keeps liability bounded |
| Credit redemption | Next renewal auto-applies a ₹2,499 credit | No manual refunds |
| Attribution | Unique invite link per subscriber (`/r?ref=<id>`) | Deterministic, cookie/session based |

## Flow

1. Pro subscriber opens **Refer** in the private Telegram channel → bot replies
   with their unique link.
2. Referred visitor lands on `/` with `?ref=<id>` → tracked in
   `sessionStorage`, attached to the `POST /api/create-order` payload
   (`referral_id` field — add to `deepstream/payments.py` +
   `netlify/functions/create-order.mjs` + the webhook `data.order` pass-through).
3. On verified `ORDER_PAID` (amount + currency checked), the referrer's credit
   ledger increments (store alongside `data/subscriptions.json`).
4. Bot messages referrer: "You earned a free month 🎉".

## Copy (for the Telegram / site flow)

> Invite a trader who takes the ocean seriously. When they subscribe, you
> get a free Pro month. Your link: {{link}}

## Honesty guardrail
Referrals must not convert into hype: referred users see the same published
track record and disclaimers as everyone else. No "guaranteed returns" copy,
ever — the referral reward is a *product* credit, not a promise of profits.

## Rollout checklist
- [ ] Add `referral_id` to create-order payload + store
- [ ] Add `/refer` bot command (invite link + credit balance)
- [ ] Add refer banner to `signal_site` pricing section
- [ ] Track conversion in Netlify analytics
