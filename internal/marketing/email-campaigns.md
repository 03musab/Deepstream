# Email Campaign Templates

Inbound-only. Every campaign points to the published track record — the product
sells itself; the emails just surface the data.

## 1. Welcome / first-touch (post-newsletter signup)

```
Subject: The ocean tells you what copper will do in ~7 weeks

Hi {{first_name}},

Thanks for joining the Deepstream signal digest.

Each Monday we publish commodity setups derived from physical ocean data —
El Niño SST anomalies, chlorophyll concentration, subsea chemical plumes —
using a walk-forward, out-of-sample engine trained on 20 years of history.

You can see this week's signal here: {{link_to_signals}}

We publish the full trade-by-trade track record so you can judge the method
before you ever pay for it:
{{link_to_performance}}

Next digest lands {{next_monday}}.

— The Deepstream desk
```

## 2. Weekly digest (automated — see content-generator.py)

Run `python internal/marketing/content-generator.py email` after each weekly
refresh. It fills the draft with real numbers from `latest_signal.json` and
`track_record.json` — no manual editing required.

## 3. Re-engagement (no opens in 30 days)

```
Subject: Your ocean signal digest is still on

Hi {{first_name}},

You signed up for the weekly signal digest but haven't opened the last few.
Here's the honest pitch again: 362 walk-forward trades, 41% win rate,
+140% cumulative — every trade generated with only the data available at the
signal date. No curve-fitting. The track record is public:

{{link_to_performance}}

If this isn't for you, no hard feelings — hit unsubscribe and we'll leave
you alone.

— The Deepstream desk
```

## 4. Pro upgrade nudge (3+ weeks of opens, never purchased)

```
Subject: Full setups, entry · stop · target

Hi {{first_name}},

The free digest shows you *which* ocean signal is live and its confidence.
Pro shows you the entire setup: entry, stop loss, and take profit, delivered
to a private Telegram channel within minutes of publication.

{{link_to_pricing}}

30 days of Pro is ₹2,499, cancel anytime. Every payment mints a fresh
single-use invite — no lock-in, no auto-renew traps.

— The Deepstream desk
```

## 5. Refund/win-back (post-cancellation)

```
Subject: The ocean missed you

Hi {{first_name}},

Your Pro access lapsed. That's fine — the signal keeps publishing either way.

If you'd like back in, your renewal is a fresh payment with a fresh invite
link: {{link_to_pricing}}

And if something about the product let you down, reply to this email. We
actually read them.

— The Deepstream desk
```

### Notes
- Send day: **Monday 06:00 UTC**, immediately after the weekly refresh runs.
- Keep HTML minimal: one hero number (cumulative return), one CTA.
- All numbers in these templates come from the generator — never hand-edit
  figures into an email.
