# Social Media Content System

Cadence: 3 organic posts/week. Zero cold outreach — post publicly, let the
track record do the selling.

## Weekly automation

`python internal/marketing/content-generator.py social` generates the
LinkedIn + X posts from live data. The generator never invents numbers:
every figure is pulled from `latest_signal.json` / `track_record.json`.

## Standing formats

### 1. Weekly signal digest (Mon, right after refresh)
From the generator. Lead with the setup, cite the track record, close with
the free channel.

### 2. Proof-of-work thread (Wed)

```
1/ We get asked "why would the ocean predict commodities?"
2/ El Niño alters rainfall around South American copper mines →
   production shocks → price moves.
3/ Chlorophyll collapse → nutrient disruption → constrained tuna catch.
4/ Physical systems precede markets. We measure the lag, then publish.
5/ 20 years of data. Granger-tested. Trade-by-trade record published:
   [link]
```

### 3. Transparency post (Fri)

```
We publish every trade — the losses included.
This week's walk-forward record:
- N trades · X% win rate · +Y% cumulative
- Generated with only the data available at each signal date
Nobody on this feed hides their losing trades. [link]
```

## Repurposing
- X thread → LinkedIn carousel (same 5 points, one slide each).
- Friday transparency post → newsletter "signal of the week" section.
- Monthly: screenshot of the equity curve + one-line comment. Visual posts
  outperform text-only ~2.5x on commodity audiences.

## Etiquette
- Never post entry/stop/target levels publicly — that's the Pro product.
- Always link the published track record; it's the moat.
- Reply to comments; never DM strangers with pitches.
