"""Core signal computation for the Deepstream engine.

Computes lagged correlations between oceanographic indicators and commodity
prices, and converts them into discrete trade setups (entry / stop / target)
with an explicit confidence grade.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd

from deepstream import config


@dataclass
class Signal:
    pair_id: int
    pair: str
    direction: str
    confidence: str
    pearson_r: float
    lag_days: int
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    ocean_change: Optional[float] = None
    price_change_pct: Optional[float] = None
    status: str = "ACTIVE"
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _grade_confidence(r: float) -> str:
    """Map an (possibly negative) Pearson r to a confidence grade.

    Uses the absolute value of the correlation, since a strong negative
    relationship is as informative as a strong positive one.
    """
    abs_r = abs(r)
    thresholds = config.CONFIDENCE_THRESHOLDS
    for grade in ("HIGH", "MEDIUM", "LOW"):
        if abs_r >= thresholds[grade]:
            return grade
    return "NOISE"


def _load_pair_data(pair_cfg: dict) -> Optional[pd.DataFrame]:
    ocean_path = config.DATA_DIR / pair_cfg["ocean_file"]
    price_path = config.DATA_DIR / pair_cfg["price_file"]
    if not ocean_path.exists() or not price_path.exists():
        return None

    ocean = pd.read_csv(ocean_path, parse_dates=["Date"]).set_index("Date")
    price = pd.read_csv(price_path, parse_dates=["Date"]).set_index("Date")

    if pair_cfg["monthly_ocean"]:
        ocean = ocean.resample("D").ffill()

    merged = pd.merge(
        price, ocean, left_index=True, right_index=True, how="inner"
    ).sort_index()
    merged = merged[~merged.index.duplicated(keep="last")]
    return merged


def compute_signal_for_pair(
    pair_id: int, params: dict, df: Optional[pd.DataFrame] = None
) -> Optional[Signal]:
    """Compute the current signal for a single pair.

    Args:
        pair_id: pair identifier from ``deepstream.config.PAIRS``.
        params: optimized parameters dict keyed by ``test_<id>``.
        df: pre-loaded merged frame; if None it is loaded from disk.

    Returns:
        A :class:`Signal` or ``None`` if the data is unusable.
    """
    pair_cfg = config.PAIRS[pair_id]
    if df is None:
        df = _load_pair_data(pair_cfg)
    if df is None or df.empty:
        return Signal(
            pair_id=pair_id,
            pair=pair_cfg["pair"],
            direction="NONE",
            confidence="NOISE",
            pearson_r=0.0,
            lag_days=0,
            status="NO_DATA",
        )

    lag = int(params.get(f"test_{pair_id}", {}).get("optimal_lag", 0))

    df = df.copy()
    df["ocean_lagged"] = df[pair_cfg["ocean_col"]].shift(lag)
    clean = df.dropna()

    if len(clean) < 30:
        return Signal(
            pair_id=pair_id,
            pair=pair_cfg["pair"],
            direction="NONE",
            confidence="NOISE",
            pearson_r=0.0,
            lag_days=lag,
            status="INSUFFICIENT_DATA",
        )

    r = float(np.corrcoef(clean[pair_cfg["price_col"]], clean["ocean_lagged"])[0, 1])
    if not np.isfinite(r):
        r = 0.0

    latest_price = float(df[pair_cfg["price_col"]].iloc[-1])

    window = max(1, min(lag, config.CHANGE_WINDOW_MAX))
    if len(df) > window:
        prev_ocean = float(df[pair_cfg["ocean_col"]].iloc[-1 - window])
        ocean_change = float(df[pair_cfg["ocean_col"]].iloc[-1]) - prev_ocean
    else:
        ocean_change = 0.0

    price_window = min(config.PRICE_WINDOW_MAX, len(df) - 1)
    price_change_pct = (
        (float(df[pair_cfg["price_col"]].iloc[-1])
         / float(df[pair_cfg["price_col"]].iloc[-1 - price_window]) - 1) * 100
    )

    confidence = _grade_confidence(abs(r))
    min_grade = config.MIN_TRADE_CONFIDENCE
    is_tradeable = confidence in ("HIGH", "MEDIUM")
    if confidence == "NOISE" or not is_tradeable:
        return Signal(
            pair_id=pair_id,
            pair=pair_cfg["pair"],
            direction="NONE",
            confidence=confidence,
            pearson_r=round(r, 4),
            lag_days=lag,
            status="NO_TRADE",
        )

    if r > 0:
        direction = "LONG" if ocean_change > 0 else "SHORT"
    else:
        direction = "SHORT" if ocean_change > 0 else "LONG"

    entry = round(latest_price, 2)
    if direction == "LONG":
        stop = round(entry * (1 - config.STOP_LOSS_PCT), 2)
        target = round(entry * (1 + config.TAKE_PROFIT_PCT), 2)
    else:
        stop = round(entry * (1 + config.STOP_LOSS_PCT), 2)
        target = round(entry * (1 - config.TAKE_PROFIT_PCT), 2)

    return Signal(
        pair_id=pair_id,
        pair=pair_cfg["pair"],
        direction=direction,
        confidence=confidence,
        pearson_r=round(r, 4),
        lag_days=lag,
        entry=entry,
        stop_loss=stop,
        take_profit=target,
        ocean_change=round(ocean_change, 4),
        price_change_pct=round(price_change_pct, 2),
        status="ACTIVE",
    )


def compute_all_signals(params: dict) -> list[Signal]:
    """Compute signals for every configured pair."""
    return [
        compute_signal_for_pair(pair_id, params)
        for pair_id in sorted(config.PAIRS)
    ]


def load_params() -> dict:
    """Load optimized parameters from disk, falling back to sane defaults."""
    if config.PARAM_FILE.exists():
        with open(config.PARAM_FILE) as f:
            return json.load(f)
    return {}


def summarize(signals: list[Signal]) -> dict[str, int]:
    """Produce a compact summary of the signal set."""
    active = [s for s in signals if s.status == "ACTIVE"]
    return {
        "total": len(signals),
        "active": len(active),
        "high_confidence": sum(1 for s in active if s.confidence == "HIGH"),
        "medium_confidence": sum(1 for s in active if s.confidence == "MEDIUM"),
    }
