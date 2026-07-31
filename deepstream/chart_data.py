"""Chart data assembly for the landing site.

Builds the time-series payload used by the interactive charts on the landing
page: recent price and ocean-indicator series per pair, plus a cumulative
equity curve derived from the walk-forward track record.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from deepstream import config
from deepstream.signal_engine import load_params


def _series_for_pair(pair_id: int, points: int = 520) -> dict[str, Any] | None:
    """Return the last ``points`` rows of price and ocean indicator."""
    pair_cfg = config.PAIRS[pair_id]
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
    merged = merged[~merged.index.duplicated(keep="last")].tail(points)

    return {
        "pair_id": pair_id,
        "name": pair_cfg["name"],
        "pair": pair_cfg["pair"],
        "ocean_col": pair_cfg["ocean_col"],
        "price_col": pair_cfg["price_col"],
        "dates": [d.strftime("%Y-%m-%d") for d in merged.index],
        "price": [round(float(v), 4) for v in merged[pair_cfg["price_col"]]],
        "ocean": [round(float(v), 4) for v in merged[pair_cfg["ocean_col"]]],
    }


def _equity_curve(track_record: dict[str, Any]) -> list[float]:
    """Cumulative return curve from the track record trade log."""
    trades = track_record.get("trades", [])
    curve = []
    cum = 0.0
    for t in sorted(trades, key=lambda x: x["signal_date"]):
        cum += t["return_pct"]
        curve.append(round(cum, 2))
    return curve


def build_chart_data() -> dict[str, Any]:
    """Assemble the full chart-data payload for the site."""
    params = load_params()

    series = []
    for pair_id in sorted(config.PAIRS):
        data = _series_for_pair(pair_id)
        if data is None:
            continue
        lag = int(params.get(f"test_{pair_id}", {}).get("optimal_lag", 0))
        data["lag_days"] = lag
        series.append(data)

    track_record = {}
    if config.TRACK_RECORD_FILE.exists():
        track_record = json.loads(config.TRACK_RECORD_FILE.read_text())

    return {
        "series": series,
        "equity": _equity_curve(track_record),
    }
