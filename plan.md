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
1. Create Stripe / LemonSqueezy payment link for the Pro tier; wire the
   `#buy-btn` URL in `signal_site/app.js`.
2. Create the private Telegram channel and add the bot; fill in `.env`.
3. Run `./run_weekly.sh` and confirm delivery.
