import os
import json
import subprocess
import sys
import pandas as pd
import numpy as np
from datetime import datetime

DATA_DIR = "data"
SIGNAL_FILE = "latest_signal.json"
PARAM_FILE = "optimized_parameters.json"

def run_step(name, script):
    print(f"=== Running {name} ===")
    result = subprocess.run([sys.executable, script], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WARNING: {script} failed (exit {result.returncode}):")
        print(result.stderr[-2000:] if result.stderr else "(no stderr)")
    return result.returncode == 0

def run_pipeline():
    ok = True
    ok &= run_step("Data Fetch", "fetch_data.py")
    ok &= run_step("Optimizer", "quant_optimizer.py")
    ok &= run_step("Backtests", "run_backtests.py")
    if not ok:
        print("WARNING: One or more pipeline steps failed. Using best available data.")

def load_params():
    if os.path.exists(PARAM_FILE):
        with open(PARAM_FILE) as f:
            return json.load(f)
    return {}

def compute_signal(params):
    test_configs = [
        {"id": 1, "name": "Pacific SST -> Copper", "ocean_file": "noaa_sst_processed.csv", "price_file": "HG_F_processed.csv", "ocean_col": "SST_Anomaly", "price_col": "HG_F_Price", "monthly_ocean": True},
        {"id": 2, "name": "Atlantic Chlorophyll -> Tuna", "ocean_file": "chlorophyll_processed.csv", "price_file": "tuna_processed.csv", "ocean_col": "Chlorophyll", "price_col": "Tuna_Price", "monthly_ocean": False},
        {"id": 3, "name": "GoM Chemical Plume -> Crude Oil", "ocean_file": "chemical_plume_processed.csv", "price_file": "CL_F_processed.csv", "ocean_col": "Chemical_Plume", "price_col": "CL_F_Price", "monthly_ocean": False},
    ]

    signals = []
    for cfg in test_configs:
        ocean_path = os.path.join(DATA_DIR, cfg["ocean_file"])
        price_path = os.path.join(DATA_DIR, cfg["price_file"])
        if not os.path.exists(ocean_path) or not os.path.exists(price_path):
            signals.append({"pair": cfg["name"], "status": "NO_DATA"})
            continue

        ocean = pd.read_csv(ocean_path, parse_dates=["Date"]).set_index("Date")
        price = pd.read_csv(price_path, parse_dates=["Date"]).set_index("Date")

        if cfg["monthly_ocean"]:
            ocean = ocean.resample("D").ffill()

        merged = pd.merge(price, ocean, left_index=True, right_index=True, how="inner").sort_index()

        lag = params.get(f"test_{cfg['id']}", {}).get("optimal_lag", 0)

        merged["ocean_lagged"] = merged[cfg["ocean_col"]].shift(lag)
        clean = merged.dropna()

        if len(clean) < 30:
            signals.append({"pair": cfg["name"], "status": "INSUFFICIENT_DATA"})
            continue

        r = np.corrcoef(clean[cfg["price_col"]], clean["ocean_lagged"])[0, 1]
        latest_ocean = merged[cfg["ocean_col"]].iloc[-1]
        latest_price = merged[cfg["price_col"]].iloc[-1]

        window = max(1, min(lag, 30))
        if len(merged) > window:
            prev_ocean = merged[cfg["ocean_col"]].iloc[-1 - window]
            ocean_change = latest_ocean - prev_ocean
        else:
            ocean_change = 0.0
        price_change_pct = ((merged[cfg["price_col"]].iloc[-1] / merged[cfg["price_col"]].iloc[-min(30, len(merged) - 1)] - 1) * 100)

        abs_r = abs(r)
        if abs_r >= 0.7:
            confidence = "HIGH"
        elif abs_r >= 0.4:
            confidence = "MEDIUM"
        elif abs_r >= 0.2:
            confidence = "LOW"
        else:
            confidence = "NOISE"

        if confidence == "NOISE":
            signals.append({
                "pair": cfg["name"],
                "direction": "NONE",
                "confidence": "NOISE",
                "pearson_r": round(r, 4),
                "lag_days": lag,
                "status": "NO_TRADE"
            })
            continue

        if r > 0:
            direction = "LONG" if ocean_change > 0 else "SHORT"
        else:
            direction = "SHORT" if ocean_change > 0 else "LONG"

        entry = round(latest_price, 2)
        sl = round(entry * 0.95, 2) if direction == "LONG" else round(entry * 1.05, 2)
        tp = round(entry * 1.08, 2) if direction == "LONG" else round(entry * 0.92, 2)

        signals.append({
            "pair": cfg["name"],
            "direction": direction,
            "confidence": confidence,
            "pearson_r": round(r, 4),
            "lag_days": lag,
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp,
            "ocean_change": round(ocean_change, 4),
            "price_change_30d_pct": round(price_change_pct, 2),
            "status": "ACTIVE"
        })

    return signals

def generate(skip_pipeline=False):
    print("=== Deepstream Signal Generator ===")
    if not skip_pipeline:
        run_pipeline()
    else:
        print("Skipping pipeline (using existing data)")

    params = load_params()
    signals = compute_signal(params)

    report = {
        "generated_at": datetime.now().isoformat(),
        "signals": signals,
        "summary": {
            "total": len(signals),
            "active": sum(1 for s in signals if s.get("status") == "ACTIVE"),
            "high_confidence": sum(1 for s in signals if s.get("confidence") == "HIGH"),
            "medium_confidence": sum(1 for s in signals if s.get("confidence") == "MEDIUM"),
        }
    }

    with open(SIGNAL_FILE, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nSignals saved to {SIGNAL_FILE}")
    print(f"Active signals: {report['summary']['active']}")
    print(f"High confidence: {report['summary']['high_confidence']}")
    for s in signals:
        if s.get("status") == "ACTIVE":
            print(f"  {s['pair']}: {s['direction']} @ {s['entry']} | r={s['pearson_r']} | {s['confidence']} confidence")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate Deepstream trading signals")
    parser.add_argument("--skip-pipeline", action="store_true",
                        help="Skip fetch/optimize/backtest steps, use existing data")
    args = parser.parse_args()
    generate(skip_pipeline=args.skip_pipeline)
