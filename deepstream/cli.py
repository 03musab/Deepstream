"""Deepstream signal platform — command line interface.

Usage:
    python -m deepstream generate [--skip-pipeline] [--verbose]
    python -m deepstream track [--verbose]
    python -m deepstream run [--verbose]   # generate + track + copy to site
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from deepstream import config
from deepstream.chart_data import build_chart_data
from deepstream.logging_setup import setup_logging
from deepstream.signal_engine import (
    compute_all_signals,
    load_params,
    summarize,
)
from deepstream.track_record import generate_track_record

logger = setup_logging()


def _run_step(name: str, script: Path) -> bool:
    logger.info("Running %s (%s)", name, script)
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True
    )
    if result.returncode != 0:
        logger.warning(
            "%s failed (exit %s):\n%s",
            script, result.returncode, (result.stderr or "")[-2000:],
        )
        return False
    logger.info("%s completed", script)
    return True


def _run_pipeline() -> bool:
    # Research/ops scripts live under scripts/ and are invoked from the repo
    # root (relative paths inside them assume the repo root as CWD).
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    steps = [
        ("Data fetch", scripts_dir / "fetch_data.py"),
        ("Parameter optimization", scripts_dir / "quant_optimizer.py"),
        ("Backtest engine", scripts_dir / "run_backtests.py"),
    ]
    ok = all(_run_step(name, script) for name, script in steps)
    if not ok:
        logger.warning("One or more pipeline steps failed; using best available data.")
    return ok


def cmd_generate(args: argparse.Namespace) -> int:
    if not args.skip_pipeline:
        _run_pipeline()

    params = load_params()
    signals = compute_all_signals(params)
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "signals": [s.to_dict() for s in signals],
        "summary": summarize(signals),
    }
    config.SIGNAL_FILE.write_text(json.dumps(report, indent=2))

    logger.info("Signals written to %s", config.SIGNAL_FILE)
    logger.info("Active: %s | HIGH: %s | MEDIUM: %s",
                report["summary"]["active"],
                report["summary"]["high_confidence"],
                report["summary"]["medium_confidence"])
    for s in signals:
        if s.status == "ACTIVE":
            logger.info("  %s: %s @ %s | r=%.4f | %s",
                        s.pair, s.direction, s.entry, s.pearson_r, s.confidence)
    return 0


def cmd_track(args: argparse.Namespace) -> int:
    params = load_params()
    record = generate_track_record(params)
    config.TRACK_RECORD_FILE.write_text(json.dumps(record, indent=2))
    stats = record["statistics"]
    logger.info("Track record written to %s", config.TRACK_RECORD_FILE)
    logger.info("Trades: %s | Wins: %s | Losses: %s | Win rate: %.1f%% | Avg return: %.2f%%",
                stats["total_trades"], stats["wins"], stats["losses"],
                stats["win_rate_pct"], stats["avg_return_pct"])
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    rc = cmd_generate(args)
    if rc:
        return rc
    if not args.no_track:
        cmd_track(args)
    _copy_to_site()
    logger.info("Site assets refreshed.")
    return 0


def _copy_to_site() -> None:
    config.SITE_SIGNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    if config.SIGNAL_FILE.exists():
        config.SITE_SIGNAL_FILE.write_text(config.SIGNAL_FILE.read_text())
    if config.TRACK_RECORD_FILE.exists():
        config.SITE_TRACK_FILE.write_text(config.TRACK_RECORD_FILE.read_text())
    # Chart data is derived from the data CSVs + track record; publish it as a
    # static asset so the charts render on static hosts (Netlify).
    config.SITE_CHART_FILE.write_text(json.dumps(build_chart_data()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deepstream", description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="verbose logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="generate latest signals")
    p_gen.add_argument("--skip-pipeline", action="store_true",
                       help="use existing data without re-running the pipeline")
    p_gen.set_defaults(func=cmd_generate)

    p_track = sub.add_parser("track", help="generate walk-forward track record")
    p_track.set_defaults(func=cmd_track)

    p_run = sub.add_parser("run", help="generate + track + refresh site assets")
    p_run.add_argument("--skip-pipeline", action="store_true")
    p_run.add_argument("--no-track", action="store_true", help="skip track record")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)

    global logger
    logger = setup_logging(verbose=args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
