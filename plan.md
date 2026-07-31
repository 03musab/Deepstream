# Deepstream — Monetization Plan

## Strategy
Run the existing backtest engine weekly to generate trading signals, deliver via Telegram/email, charge $20-50/mo.

## Phase 1 — Signal Generator (Day 1)
- [x] **Reuse `run_backtests.py`** as weekly signal engine
- [ ] Create `generate_signal.py` — wraps pipeline, outputs a concise signal report
- [ ] Output format: which pair to trade, direction (long/short), confidence score, optimal lag
- [ ] Save latest signal as JSON (`latest_signal.json`)

## Phase 2 — Landing Page (Day 1-2)
- [ ] Simplify `index.html` into a sales-focused landing page: `signal_site/index.html`
- [ ] Remove ARR modeler, fleet stats, demo mode
- [ ] Keep: value proposition, sample signal preview, pricing tiers, payment button
- [ ] Add email capture form (basic — no backend, just mailto or Formspree)

## Phase 3 — Delivery Channel (Day 2)
- [ ] Telegram bot (`telegram_bot.py`) that sends latest signal to subscribers
- [ ] Free tier: weekly summary (3 pairs, direction)
- [ ] Paid tier: entry price, stop-loss, take-profit levels
- [ ] Manual subscription management (simple text file)

## Phase 4 — Payments (Day 2-3)
- [ ] Stripe payment link (no code needed, just a buy button)
- [ ] OR LemonSqueezy for simpler setup
- [ ] After payment: send invite link to private Telegram channel

## Revenue Model
| Tier | Price | Delivery | Content |
|------|-------|----------|---------|
| Free  | $0    | Public TG channel | Weekly direction summary |
| Pro   | $29/mo | Private TG channel | Entry/SL/TP + confidence score |

## Pipeline Flow
```
fetch_data.py (weekly refresh)
  -> quant_optimizer.py (re-optimize params)
  -> run_backtests.py (run signals)
  -> generate_signal.py (format report)
  -> telegram_bot.py (deliver to subscribers)
```

## Files to Create
| File | Purpose |
|------|---------|
| `generate_signal.py` | Wraps pipeline, outputs `latest_signal.json` |
| `telegram_bot.py` | Sends signals to Telegram subscribers |
| `signal_site/index.html` | Landing page with pricing + buy button |
| `signal_site/style.css` | Landing page styles |

## Existing Files to Keep
- All `data/*` CSV files
- `quant_optimizer.py`
- `run_backtests.py`
- `quant_econometrics.py`
- `intense_tests.py`
- `fetch_data.py`
