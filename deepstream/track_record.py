"""Walk-forward track record generator.

Unlike a naive in-sample backtest, this module replays the signal engine
historically: on each past decision date, it only uses data available *up to
that date*, emits the same trade setup a subscriber would have received, and
then measures the actual forward outcome. This is the honest way to present a
performance record and is the core credibility feature of the platform.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

from deepstream import config
from deepstream.signal_engine import Signal, _load_pair_data, _grade_confidence


@dataclass
class TrackRecordEntry:
    pair_id: int
    pair: str
    signal_date: str
    direction: str
    confidence: str
    pearson_r: float
    entry: float
    stop_loss: float
    take_profit: float
    outcome: str          # WIN / LOSS / FLAT / OPEN
    return_pct: float     # realised return % for the trade
    days_to_close: int


def _simulate_trade(
    df: pd.DataFrame, entry_idx: int, direction: str,
    entry: float, stop: float, target: float, holding_days: int,
) -> tuple[str, float, int]:
    """Walk forward from ``entry_idx`` and resolve the trade outcome.

    Uses closing prices only. A trade is closed at the stop or target the first
    day the close crosses the level; otherwise it is marked to market at the
    end of the holding horizon. This is conservative — it ignores intraday
    highs/lows, so it does not overstate hits.
    """
    price_col = None
    for col in df.columns:
        if str(col).endswith("_Price"):
            price_col = col
            break
    if price_col is None:
        price_col = df.columns[0]

    horizon = min(holding_days, len(df) - entry_idx - 1)
    for offset in range(1, horizon + 1):
        close = float(df.iloc[entry_idx + offset][price_col])
        if direction == "LONG":
            if close <= stop:
                return "LOSS", -config.STOP_LOSS_PCT * 100, offset
            if close >= target:
                return "WIN", config.TAKE_PROFIT_PCT * 100, offset
        else:
            if close >= stop:
                return "LOSS", -config.STOP_LOSS_PCT * 100, offset
            if close <= target:
                return "WIN", config.TAKE_PROFIT_PCT * 100, offset

    if horizon <= 0:
        return "OPEN", 0.0, 0
    final = float(df.iloc[entry_idx + horizon][price_col])
    ret = (final / entry - 1) * 100
    if direction == "SHORT":
        ret = -ret
    if abs(ret) < 0.001:
        return "FLAT", ret, horizon
    return "OPEN", round(ret, 2), horizon


def _build_signal_at(df: pd.DataFrame, pair_cfg: dict, params: dict, date_idx: int) -> Optional[Signal]:
    """Emit the trade setup the engine would have produced on ``date_idx``."""
    lag = int(params.get(f"test_{pair_cfg['id']}", {}).get("optimal_lag", 0))

    window = df.iloc[: date_idx + 1]
    if len(window) < 100:
        return None

    lagged = window[pair_cfg["ocean_col"]].shift(lag)
    clean = pd.DataFrame({
        "price": window[pair_cfg["price_col"]],
        "ocean": lagged,
    }).dropna()

    if len(clean) < 30:
        return None

    r = float(np.corrcoef(clean["price"], clean["ocean"])[0, 1])
    if not np.isfinite(r):
        return None

    ocean_change = float(window[pair_cfg["ocean_col"]].iloc[-1]) - float(
        window[pair_cfg["ocean_col"]].iloc[max(0, len(window) - max(1, min(lag, config.CHANGE_WINDOW_MAX)))]
    )

    confidence = _grade_confidence(abs(r))
    if confidence == "NOISE" or confidence not in ("HIGH", "MEDIUM"):
        return None

    direction = (
        "LONG" if ocean_change > 0 else "SHORT"
    ) if r > 0 else (
        "SHORT" if ocean_change > 0 else "LONG"
    )

    entry = float(df.iloc[date_idx][pair_cfg["price_col"]])
    if direction == "LONG":
        stop = round(entry * (1 - config.STOP_LOSS_PCT), 4)
        target = round(entry * (1 + config.TAKE_PROFIT_PCT), 4)
    else:
        stop = round(entry * (1 + config.STOP_LOSS_PCT), 4)
        target = round(entry * (1 - config.TAKE_PROFIT_PCT), 4)

    return Signal(
        pair_id=pair_cfg["id"],
        pair=pair_cfg["pair"],
        direction=direction,
        confidence=confidence,
        pearson_r=round(r, 4),
        lag_days=lag,
        entry=round(entry, 2),
        stop_loss=stop,
        take_profit=target,
        status="ACTIVE",
    )


def generate_track_record(params: dict) -> dict[str, Any]:
    """Replay the engine over the last N years and record outcomes.

    Returns a dict with the full trade log and aggregate statistics.
    """
    records: list[TrackRecordEntry] = []

    for pair_id, pair_cfg in config.PAIRS.items():
        df = _load_pair_data(pair_cfg)
        if df is None or len(df) < 300:
            continue

        start = df.index[-1] - pd.Timedelta(days=config.TRACK_LOOKBACK_DAYS)
        window = df.loc[df.index >= start]
        # Exclude the most recent horizon so outcomes are fully realised.
        usable = window.iloc[: -config.TRACK_HOLDING_DAYS] if len(window) > config.TRACK_HOLDING_DAYS else window

        dates = usable.index[:: config.TRACK_STEP_DAYS]
        for date_idx, dt in enumerate(dates):
            pos = df.index.get_indexer([dt])[0]
            sig = _build_signal_at(df, pair_cfg, params, pos)
            if sig is None:
                continue
            if len(df) <= pos + 1:
                continue

            outcome, ret, days = _simulate_trade(
                df, pos, sig.direction, sig.entry, sig.stop_loss,
                sig.take_profit, config.TRACK_HOLDING_DAYS,
            )
            records.append(
                TrackRecordEntry(
                    pair_id=pair_id,
                    pair=pair_cfg["pair"],
                    signal_date=pd.Timestamp(dt).strftime("%Y-%m-%d"),
                    direction=sig.direction,
                    confidence=sig.confidence,
                    pearson_r=sig.pearson_r,
                    entry=sig.entry,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    outcome=outcome,
                    return_pct=ret,
                    days_to_close=days,
                )
            )

    stats = _aggregate(records)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "methodology": {
            "type": "walk-forward, out-of-sample",
            "holding_days": config.TRACK_HOLDING_DAYS,
            "step_days": config.TRACK_STEP_DAYS,
            "lookback_days": config.TRACK_LOOKBACK_DAYS,
            "risk": {
                "stop_loss_pct": config.STOP_LOSS_PCT,
                "take_profit_pct": config.TAKE_PROFIT_PCT,
            },
            "note": (
                "Every trade was generated using only data available at the "
                "signal date. No lookahead bias. Simulated results for "
                "educational purposes and do not reflect real execution, "
                "slippage, or costs."
            ),
        },
        "statistics": stats,
        "trades": [asdict(r) for r in records],
    }


def _aggregate(records: list[TrackRecordEntry]) -> dict[str, Any]:
    """Compute aggregate statistics from the trade log."""
    if not records:
        return {"total_trades": 0}

    closed = [r for r in records if r.outcome in ("WIN", "LOSS")]
    resolved = [r for r in records if r.outcome in ("WIN", "LOSS", "OPEN", "FLAT")]

    wins = sum(1 for r in records if r.outcome == "WIN")
    losses = sum(1 for r in records if r.outcome == "LOSS")

    returns = [r.return_pct for r in resolved]
    avg_return = float(np.mean(returns)) if returns else 0.0
    total_return = float(np.sum(returns)) if returns else 0.0

    win_rate = (wins / len(closed) * 100) if closed else 0.0
    avg_win = float(np.mean([r.return_pct for r in records if r.outcome == "WIN"])) if wins else 0.0
    avg_loss = float(np.mean([r.return_pct for r in records if r.outcome == "LOSS"])) if losses else 0.0

    by_pair: dict[str, dict[str, Any]] = {}
    for pair_id, pair_cfg in config.PAIRS.items():
        pair_records = [r for r in records if r.pair_id == pair_id]
        pair_closed = [r for r in pair_records if r.outcome in ("WIN", "LOSS")]
        pair_wins = sum(1 for r in pair_closed if r.outcome == "WIN")
        by_pair[pair_cfg["name"]] = {
            "trades": len(pair_records),
            "wins": pair_wins,
            "losses": len(pair_closed) - pair_wins,
            "win_rate_pct": round(pair_wins / len(pair_closed) * 100, 1) if pair_closed else 0.0,
            "avg_return_pct": round(float(np.mean([r.return_pct for r in pair_records])), 2) if pair_records else 0.0,
        }

    return {
        "total_trades": len(records),
        "closed_trades": len(closed),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(win_rate, 1),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "avg_return_pct": round(avg_return, 2),
        "total_return_pct": round(total_return, 2),
        "by_pair": by_pair,
    }
