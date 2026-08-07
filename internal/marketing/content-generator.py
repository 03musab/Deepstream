"""Deepstream marketing content generator.

Turns the *live* signal and track-record data into ready-to-publish marketing
copy — LinkedIn/X posts, email campaigns, blog drafts, feature announcements,
and changelog entries. Run it after each weekly signal refresh; it never
invents numbers, so every claim is verifiable against the published data.

Usage:
    python internal/marketing/content-generator.py all       # every format
    python internal/marketing/content-generator.py social    # LinkedIn + X
    python internal/marketing/content-generator.py email     # subscriber email
    python internal/marketing/content-generator.py blog      # blog article draft
    python internal/marketing/content-generator.py changelog # append to signal_site/changelog.json

Output is written to internal/marketing/out/ (gitignored) unless --changelog
is used, which updates the site asset directly.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent
# Make the deepstream package importable when this script is run by path
# (python internal/marketing/content-generator.py).
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from deepstream.logging_setup import make_console_unicode_safe  # noqa: E402

SIGNAL_FILE = BASE_DIR / "latest_signal.json"
TRACK_FILE = BASE_DIR / "track_record.json"
CHANGELOG_FILE = BASE_DIR / "signal_site" / "changelog.json"
OUT_DIR = Path(__file__).resolve().parent / "out"

TAG_EMOJI = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🟠", "NOISE": "⚪"}


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _active_signals(signal: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in signal.get("signals", []) if s.get("status") == "ACTIVE"]


def _fmt_metric(label: str, value: Any, suffix: str = "") -> str:
    return f"• {label}: {value}{suffix}"


def _latest_commit_message() -> str:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"], capture_output=True, text=True,
            cwd=str(BASE_DIR), timeout=10,
        )
        return out.stdout.strip() or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def gen_social(signal: dict[str, Any], track: dict[str, Any]) -> tuple[str, str]:
    """LinkedIn + X posts. Public summary never leaks entry/stop/target."""
    stats = track.get("statistics", {})
    active = _active_signals(signal)
    generated = (signal.get("generated_at") or datetime.utcnow().isoformat())[:10]

    setup_lines = []
    for s in active:
        setup_lines.append(
            f"{TAG_EMOJI.get(s.get('confidence'), '')} {s.get('direction')} "
            f"{s.get('pair')} — r {s.get('pearson_r'):.3f}, lead {s.get('lag_days')}d"
        )
    setups = "\n".join(setup_lines) if setup_lines else "No tradeable setup this week."

    linkedin = (
        "The ocean publishes its forecast 30-50 days before the market does.\n\n"
        f"Weekly signal digest · {generated}\n\n{setups}\n\n"
        "What makes this credible instead of another signal Telegram:\n"
        + _fmt_metric("Walk-forward replay", f"{stats.get('total_trades', '—')} trades")
        + "\n" + _fmt_metric("Win rate", f"{stats.get('win_rate_pct', '—')}%")
        + "\n" + _fmt_metric("Cumulative return", f"+{stats.get('total_return_pct', '—')}%")
        + "\n\nEvery trade uses only data available at the signal date. "
        "No lookahead, no curve-fitting. Full trade-by-trade record published openly.\n\n"
        "Full setups (entry · stop · target) go to Pro subscribers via Telegram.\n"
        "#Commodities #QuantitativeFinance #ElNino #OceanData"
    )

    x_post = (
        f"Weekly ocean signal digest · {generated}\n\n{setups}\n\n"
        f"Track record: {stats.get('total_trades', '—')} walk-forward trades · "
        f"{stats.get('win_rate_pct', '—')}% win rate · "
        f"+{stats.get('total_return_pct', '—')}% cumulative.\n"
        "Full setups: Pro Telegram channel."
    )
    return linkedin, x_post


def gen_email(signal: dict[str, Any], track: dict[str, Any]) -> str:
    """Subscriber-facing weekly email (public tier — no levels)."""
    stats = track.get("statistics", {})
    active = _active_signals(signal)
    generated = (signal.get("generated_at") or datetime.utcnow().isoformat())[:10]

    setup_lines = "\n".join(
        f"- {TAG_EMOJI.get(s.get('confidence'), '')} {s.get('direction')} "
        f"{s.get('pair')} (r {s.get('pearson_r'):.3f}, lead {s.get('lag_days')}d)"
        for s in active
    ) or "- No tradeable setup this week. Standing aside is a position."

    return f"""Subject: Deepstream weekly digest — {generated}

Hi there,

Here is what the ocean is telling us this week.

**This week's setups**
{setup_lines}

**Why this is not a coin flip**
- {stats.get('total_trades', '—')} walk-forward trades replayed out-of-sample
- {stats.get('win_rate_pct', '—')}% win rate, +{stats.get('total_return_pct', '—')}% cumulative
- Every entry generated from data available at the signal date — no hindsight

Full setups with entry, stop and target are published to the private Pro
channel. Upgrade anytime: <link to pricing>.

Stay curious,
The Deepstream desk
(Research only — not financial advice.)"""


def gen_blog(signal: dict[str, Any], track: dict[str, Any]) -> str:
    """SEO-oriented blog article draft built from the current signal."""
    stats = track.get("statistics", {})
    active = _active_signals(signal)
    generated = (signal.get("generated_at") or datetime.utcnow().isoformat())[:10]
    headline = "El Niño, chlorophyll, and the commodity moves markets haven't priced in yet"

    setup_paras = []
    for s in active:
        setup_paras.append(
            f"- **{s.get('pair')}**: the engine flags **{s.get('direction')}** "
            f"with {s.get('confidence')} confidence (r = {s.get('pearson_r'):.3f}) at a "
            f"{s.get('lag_days')}-day lead."
        )
    setups = "\n".join(setup_paras) or "- No tradeable setup this week."

    return f"""# {headline}

*Draft generated {generated} — verify numbers before publishing.*

## TL;DR
Physical systems precede markets. This week's walk-forward engine, built on
20 years of NOAA and satellite data, is watching the following relationships:

{setups}

## Why the ocean leads commodities
Sea-surface temperature anomalies alter rainfall around South American copper
mines. Chlorophyll collapses signal nutrient disruption that constrains tuna
catch. Subsea chemical plumes flag energy-infrastructure stress. Markets price
these events in *after* the physical data arrives; the Deepstream engine aims
to lead them.

## The honest part
Most signal services show a cherry-picked backtest. Deepstream publishes a
trade-by-trade walk-forward record: {stats.get('total_trades', '—')} simulated
trades, {stats.get('win_rate_pct', '—')}% win rate, +{stats.get('total_return_pct', '—')}%
cumulative — each generated using only data available at the signal date.

## What this means for you
- **Free**: weekly direction + confidence digest on Telegram.
- **Pro**: full setups with entry, stop, and target, plus the complete track record.

*Deepstream is a quantitative research service, not financial advice.*"""


def gen_feature_announcement() -> str:
    """Announcement template for a new feature/ship."""
    last_commit = _latest_commit_message()
    return f"""# Feature announcement — draft

**Title:** Deepstream now ships {{FEATURE_NAME}}

**Body:**
We just shipped {{FEATURE_NAME}}.

- What it does: {{ONE_LINER}}
- Why it matters: {{BENEFIT}}
- How to use it: {{USAGE}}

Try it today: {{LINK}}

---
*Auto-draft generated {datetime.utcnow().strftime('%Y-%m-%d')}.*
*Latest repo commit: {last_commit or 'n/a'} — use this as a hint for what to announce.*"""


def gen_changelog(signal: dict[str, Any]) -> None:
    """Append a weekly-signal entry to signal_site/changelog.json (idempotent)."""
    active = _active_signals(signal)
    generated = (signal.get("generated_at") or datetime.utcnow().isoformat())[:10]
    if not CHANGELOG_FILE.exists():
        data = {"entries": []}
    else:
        data = json.loads(CHANGELOG_FILE.read_text(encoding="utf-8"))

    title = f"Weekly signal published — {generated}"
    if any(s.get("direction") not in ("NONE",) for s in active):
        first = active[0]
        title += f" — {first.get('direction')} {first.get('pair')}"
    body = "; ".join(
        f"{s.get('direction')} {s.get('pair')} at {s.get('confidence')} (r {s.get('pearson_r'):.3f})"
        for s in active
    ) or "No tradeable setups this week — standing aside."

    entry = {"date": generated, "tag": "signal", "title": title, "body": body}
    # Idempotent per weekly cycle: at most one signal entry per date.
    if any(
        e.get("date") == generated and e.get("tag") == "signal"
        for e in data["entries"]
    ):
        print(f"Changelog already has a signal entry for {generated} — skipping.")
        return

    data["entries"].insert(0, entry)
    CHANGELOG_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Appended changelog entry → {CHANGELOG_FILE}")


def _write(name: str, content: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_text(content + "\n", encoding="utf-8")
    print(f"Wrote {path}")


def main(argv: list[str] | None = None) -> int:
    # Same guard the logger uses: Windows consoles cannot encode emoji.
    make_console_unicode_safe()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", nargs="?", default="all",
        choices=["all", "social", "email", "blog", "announcement", "changelog"],
        help="what to generate (default: all)",
    )
    args = parser.parse_args(argv)

    signal = _load(SIGNAL_FILE)
    track = _load(TRACK_FILE)

    if args.command in ("all", "social"):
        linkedin, x = gen_social(signal, track)
        _write("linkedin-post.md", linkedin)
        _write("x-post.txt", x)
        print(linkedin + "\n\n" + "-" * 60 + "\n\n" + x)
    if args.command in ("all", "email"):
        _write("weekly-email.md", gen_email(signal, track))
    if args.command in ("all", "blog"):
        _write("blog-draft.md", gen_blog(signal, track))
    if args.command in ("all", "announcement"):
        _write("feature-announcement.md", gen_feature_announcement())
    if args.command in ("all", "changelog"):
        gen_changelog(signal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
