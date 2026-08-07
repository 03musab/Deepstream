import os
import json
import pandas as pd
import numpy as np
from multiprocessing import Pool, cpu_count
from datetime import datetime

DATA_DIR = "data"

def load_and_prepare(test_num):
    if test_num == 1:
        # SST (monthly) vs Copper (daily)
        sst = pd.read_csv(os.path.join(DATA_DIR, "noaa_sst_processed.csv"), parse_dates=['Date']).set_index('Date')
        comm = pd.read_csv(os.path.join(DATA_DIR, "HG_F_processed.csv"), parse_dates=['Date']).set_index('Date')
        sst_daily = sst.resample('D').ffill()
        merged = pd.merge(comm, sst_daily, left_index=True, right_index=True, how='inner')
        return merged, "HG_F_Price", "SST_Anomaly"
    elif test_num == 2:
        # Chlorophyll (daily) vs Tuna (daily)
        chlo = pd.read_csv(os.path.join(DATA_DIR, "chlorophyll_processed.csv"), parse_dates=['Date']).set_index('Date')
        tuna = pd.read_csv(os.path.join(DATA_DIR, "tuna_processed.csv"), parse_dates=['Date']).set_index('Date')
        merged = pd.merge(tuna, chlo, left_index=True, right_index=True, how='inner')
        return merged, "Tuna_Price", "Chlorophyll"
    else:
        # Chemical Plumes (daily) vs WTI Crude Oil (daily)
        plume = pd.read_csv(os.path.join(DATA_DIR, "chemical_plume_processed.csv"), parse_dates=['Date']).set_index('Date')
        oil = pd.read_csv(os.path.join(DATA_DIR, "CL_F_processed.csv"), parse_dates=['Date']).set_index('Date')
        merged = pd.merge(oil, plume, left_index=True, right_index=True, how='inner')
        return merged, "CL_F_Price", "Chemical_Plume"

def evaluate_combination(args):
    """Evaluates a single grid cell: (data_chunk, comm_col, ocean_col, ocean_window, price_window, lag)"""
    df_raw, comm_col, ocean_col, o_win, p_win, lag = args
    
    df = df_raw.copy()
    
    # Apply rolling smoothing
    if o_win > 1:
        df['ocean_smooth'] = df[ocean_col].rolling(window=o_win).mean()
    else:
        df['ocean_smooth'] = df[ocean_col]
        
    if p_win > 1:
        df['price_smooth'] = df[comm_col].rolling(window=p_win).mean()
    else:
        df['price_smooth'] = df[comm_col]
        
    # Apply lag
    df['ocean_lagged'] = df['ocean_smooth'].shift(lag)
    
    clean = df[['price_smooth', 'ocean_lagged']].dropna()
    if len(clean) < 100:
        return (o_win, p_win, lag, 0.0)
        
    r = np.corrcoef(clean['price_smooth'], clean['ocean_lagged'])[0, 1]
    r = 0.0 if np.isnan(r) else r
    return (o_win, p_win, lag, r)

def optimize_test(test_num):
    df, comm_col, ocean_col = load_and_prepare(test_num)
    
    # Define grid search parameters
    ocean_windows = [1, 5, 10, 20, 30, 45, 60, 90, 120]
    price_windows = [1, 5, 10, 20, 30, 45, 60, 90, 120]
    lags = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 56, 60, 70, 80, 90, 100, 110, 120]
    
    tasks = []
    for o_win in ocean_windows:
        for p_win in price_windows:
            for lag in lags:
                tasks.append((df, comm_col, ocean_col, o_win, p_win, lag))
                
    # Use Multiprocessing to process in parallel
    num_workers = cpu_count()
    print(f"Test {test_num}: Parallel grid search size = {len(tasks)} tasks using {num_workers} CPU workers...")
    
    with Pool(num_workers) as pool:
        results = pool.map(evaluate_combination, tasks)
        
    # Find combination that maximizes absolute correlation coefficient
    best_res = max(results, key=lambda x: abs(x[3]))
    return {
        "ocean_window": best_res[0],
        "price_window": best_res[1],
        "optimal_lag": best_res[2],
        "max_correlation": best_res[3]
    }

def main():
    print("=========================================================")
    print("      NEPTUNE MULTICORE GRID-SEARCH OPTIMIZER            ")
    print("=========================================================")
    
    start_time = datetime.now()
    
    optimized = {}
    for test_num in [1, 2, 3]:
        print(f"\nOptimizing Test {test_num}...")
        res = optimize_test(test_num)
        optimized[f"test_{test_num}"] = res
        print(f"Optimal Parameters Found:")
        print(f"  * Ocean Smoothing: {res['ocean_window']} Days")
        print(f"  * Price Smoothing: {res['price_window']} Days")
        print(f"  * Lead Time (Lag): {res['optimal_lag']} Days")
        print(f"  * Optimized Pearson Correlation: r = {res['max_correlation']:.4f}")
        
    # Save parameters
    with open("optimized_parameters.json", "w") as f:
        json.dump(optimized, f, indent=4)
        
    elapsed = (datetime.now() - start_time).total_seconds()
    print("\n=========================================================")
    print(f"Optimization finished in {elapsed:.2f} seconds!")
    print("Parameters saved to optimized_parameters.json")
    print("=========================================================")

if __name__ == "__main__":
    main()
