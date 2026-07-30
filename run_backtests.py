import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Setup directories
DATA_DIR = "data"
PLOTS_DIR = "plots"
os.makedirs(PLOTS_DIR, exist_ok=True)

def calculate_sharpe_and_hitrate(ocean_series, price_series, is_negative_correlation=False):
    # Simple trading strategy simulation:
    # Position = +1 if ocean_series > 0, -1 if ocean_series < 0 (or vice versa if negative correlation)
    # Return of strategy = Position * Daily Return of commodity
    df = pd.DataFrame({'ocean': ocean_series, 'price': price_series}).dropna()
    df['returns'] = df['price'].pct_change()
    
    if is_negative_correlation:
        df['position'] = np.where(df['ocean'] > df['ocean'].median(), -1, 1)
    else:
        df['position'] = np.where(df['ocean'] > df['ocean'].median(), 1, -1)
        
    df['strategy_returns'] = df['position'].shift(1) * df['returns']
    df = df.dropna()
    
    # Calculate Sharpe (annualized, assuming 252 trading days)
    mean_ret = df['strategy_returns'].mean()
    std_ret = df['strategy_returns'].std()
    sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0
    
    # Hit rate: percentage of days with positive strategy returns out of non-zero return days
    non_zero = df[df['returns'] != 0]
    hits = non_zero[non_zero['strategy_returns'] > 0]
    hit_rate = len(hits) / len(non_zero) if len(non_zero) > 0 else 0
    
    return sharpe, hit_rate

def run_test_1():
    print("\n--- Running Test 1: Pacific SST Anomaly vs. Copper Futures (8-Week Lead) ---")
    sst_path = os.path.join(DATA_DIR, "noaa_sst_processed.csv")
    copper_path = os.path.join(DATA_DIR, "HG_F_processed.csv")
    
    if not os.path.exists(sst_path) or not os.path.exists(copper_path):
        print("Missing data files for Test 1. Run fetch_data.py first.")
        return None
        
    sst = pd.read_csv(sst_path, parse_dates=['Date'])
    copper = pd.read_csv(copper_path, parse_dates=['Date'])
    
    # SST is monthly, Copper is daily. Let's merge them.
    # Set Date as index, resample SST to daily and forward fill
    sst.set_index('Date', inplace=True)
    sst_daily = sst.resample('D').ffill()
    
    # Merge on Date index
    merged = pd.merge(copper, sst_daily, left_on='Date', right_index=True, how='inner')
    merged.sort_values('Date', inplace=True)
    
    # Shift SST anomaly by 56 days (8 weeks) forward to represent lead time
    merged['SST_Anomaly_Lagged'] = merged['SST_Anomaly'].shift(56)
    
    # Drop NaNs
    df_clean = merged.dropna()
    
    # Correlations
    r_no_lag = np.corrcoef(df_clean['SST_Anomaly'], df_clean['HG_F_Price'])[0, 1]
    r_lagged = np.corrcoef(df_clean['SST_Anomaly_Lagged'], df_clean['HG_F_Price'])[0, 1]
    
    sharpe, hit_rate = calculate_sharpe_and_hitrate(df_clean['SST_Anomaly_Lagged'], df_clean['HG_F_Price'])
    
    print(f"Unlagged Correlation (SST vs Copper): r = {r_no_lag:.4f}")
    print(f"Lagged Correlation (SST lagged 8 weeks vs Copper): r = {r_lagged:.4f}")
    print(f"Simulated Strategy Sharpe Ratio: {sharpe:.2f}")
    print(f"Simulated Strategy Hit Rate: {hit_rate:.2%}")
    
    # Lead-lag sweep (-120 to +120 days)
    lags = range(-120, 121, 2)
    corrs = []
    for l in lags:
        temp_lagged = merged['SST_Anomaly'].shift(l)
        temp_df = pd.DataFrame({'lagged': temp_lagged, 'price': merged['HG_F_Price']}).dropna()
        c = np.corrcoef(temp_df['lagged'], temp_df['price'])[0, 1]
        corrs.append(c)
        
    # Plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    # Time Series Overlay
    ax1.plot(df_clean['Date'], df_clean['HG_F_Price'], color='#4facfe', label='Copper Futures ($/lb)')
    ax1_twin = ax1.twinx()
    ax1_twin.plot(df_clean['Date'], df_clean['SST_Anomaly_Lagged'], color='#ff6b6b', alpha=0.7, label='SST Anomaly (Lagged 8w)')
    ax1.set_title("Pacific SST Anomaly (Lagged 8 Weeks) vs. Copper Futures Prices")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Copper Price ($/lb)")
    ax1_twin.set_ylabel("SST Anomaly (°C)")
    ax1.grid(True, linestyle='--', alpha=0.3)
    
    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_twin.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    # Lead-Lag Curve
    ax2.plot(lags, corrs, color='#00e676', linewidth=2)
    ax2.axvline(x=56, color='#ff6b6b', linestyle='--', label='Target Lead: 56 Days (8 Weeks)')
    ax2.set_title("Lead-Lag Correlation Analysis (SST leading Copper)")
    ax2.set_xlabel("Ocean Signal Lag (Days)")
    ax2.set_ylabel("Pearson Correlation Coefficient (r)")
    ax2.grid(True, linestyle='--', alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    plot_path = os.path.join(PLOTS_DIR, "test1_sst_copper.png")
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"Saved correlation diagnostic plot to {plot_path}")
    
    return r_lagged, sharpe, hit_rate

def run_test_2():
    print("\n--- Running Test 2: Atlantic Chlorophyll Drop vs. North Sea Tuna Price (4-Week Lead) ---")
    chlo_path = os.path.join(DATA_DIR, "chlorophyll_processed.csv")
    tuna_path = os.path.join(DATA_DIR, "tuna_processed.csv")
    
    if not os.path.exists(chlo_path) or not os.path.exists(tuna_path):
        print("Missing data files for Test 2. Run fetch_data.py first.")
        return None
        
    chlo = pd.read_csv(chlo_path, parse_dates=['Date'])
    tuna = pd.read_csv(tuna_path, parse_dates=['Date'])
    
    merged = pd.merge(tuna, chlo, on='Date', how='inner')
    merged.sort_values('Date', inplace=True)
    
    # Shift Chlorophyll by 28 days (4 weeks) forward
    merged['Chlorophyll_Lagged'] = merged['Chlorophyll'].shift(28)
    df_clean = merged.dropna()
    
    r_no_lag = np.corrcoef(df_clean['Chlorophyll'], df_clean['Tuna_Price'])[0, 1]
    r_lagged = np.corrcoef(df_clean['Chlorophyll_Lagged'], df_clean['Tuna_Price'])[0, 1]
    
    # This is a negative correlation (chlorophyll drops lead to tuna price spikes)
    sharpe, hit_rate = calculate_sharpe_and_hitrate(df_clean['Chlorophyll_Lagged'], df_clean['Tuna_Price'], is_negative_correlation=True)
    
    print(f"Unlagged Correlation (Chlorophyll vs Tuna): r = {r_no_lag:.4f}")
    print(f"Lagged Correlation (Chlorophyll lagged 4 weeks vs Tuna): r = {r_lagged:.4f}")
    print(f"Simulated Strategy Sharpe Ratio: {sharpe:.2f}")
    print(f"Simulated Strategy Hit Rate: {hit_rate:.2%}")
    
    # Lead-lag sweep
    lags = range(-60, 61, 1)
    corrs = []
    for l in lags:
        temp_lagged = merged['Chlorophyll'].shift(l)
        temp_df = pd.DataFrame({'lagged': temp_lagged, 'price': merged['Tuna_Price']}).dropna()
        c = np.corrcoef(temp_df['lagged'], temp_df['price'])[0, 1]
        corrs.append(c)
        
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    # Time Series Overlay
    ax1.plot(df_clean['Date'], df_clean['Tuna_Price'], color='#e91e63', label='North Sea Tuna Price ($/kg)')
    ax1_twin = ax1.twinx()
    ax1_twin.plot(df_clean['Date'], df_clean['Chlorophyll_Lagged'], color='#00e676', alpha=0.7, label='Chlorophyll (Lagged 4w)')
    ax1.set_title("Atlantic Chlorophyll (Lagged 4 Weeks) vs. Tuna Prices")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Tuna Price ($/kg)")
    ax1_twin.set_ylabel("Chlorophyll Index (mg/m³)")
    ax1.grid(True, linestyle='--', alpha=0.3)
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_twin.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    # Lead-Lag Curve
    ax2.plot(lags, corrs, color='#ab47bc', linewidth=2)
    ax2.axvline(x=28, color='#ff6b6b', linestyle='--', label='Target Lead: 28 Days (4 Weeks)')
    ax2.set_title("Lead-Lag Correlation Analysis (Chlorophyll leading Tuna)")
    ax2.set_xlabel("Ocean Signal Lag (Days)")
    ax2.set_ylabel("Pearson Correlation Coefficient (r)")
    ax2.grid(True, linestyle='--', alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    plot_path = os.path.join(PLOTS_DIR, "test2_chlorophyll_tuna.png")
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"Saved correlation diagnostic plot to {plot_path}")
    
    return r_lagged, sharpe, hit_rate

def run_test_3():
    print("\n--- Running Test 3: Gulf of Mexico Chemical Plume vs. Crude Oil Futures (2-Week Lead) ---")
    plume_path = os.path.join(DATA_DIR, "chemical_plume_processed.csv")
    oil_path = os.path.join(DATA_DIR, "CL_F_processed.csv")
    
    if not os.path.exists(plume_path) or not os.path.exists(oil_path):
        print("Missing data files for Test 3. Run fetch_data.py first.")
        return None
        
    plume = pd.read_csv(plume_path, parse_dates=['Date'])
    oil = pd.read_csv(oil_path, parse_dates=['Date'])
    
    merged = pd.merge(oil, plume, on='Date', how='inner')
    merged.sort_values('Date', inplace=True)
    
    # Shift Plume by 14 days (2 weeks) forward
    merged['Chemical_Plume_Lagged'] = merged['Chemical_Plume'].shift(14)
    df_clean = merged.dropna()
    
    r_no_lag = np.corrcoef(df_clean['Chemical_Plume'], df_clean['CL_F_Price'])[0, 1]
    r_lagged = np.corrcoef(df_clean['Chemical_Plume_Lagged'], df_clean['CL_F_Price'])[0, 1]
    
    sharpe, hit_rate = calculate_sharpe_and_hitrate(df_clean['Chemical_Plume_Lagged'], df_clean['CL_F_Price'])
    
    print(f"Unlagged Correlation (Chemical Plume vs Oil): r = {r_no_lag:.4f}")
    print(f"Lagged Correlation (Plume lagged 2 weeks vs Oil): r = {r_lagged:.4f}")
    print(f"Simulated Strategy Sharpe Ratio: {sharpe:.2f}")
    print(f"Simulated Strategy Hit Rate: {hit_rate:.2%}")
    
    # Lead-lag sweep
    lags = range(-30, 31, 1)
    corrs = []
    for l in lags:
        temp_lagged = merged['Chemical_Plume'].shift(l)
        temp_df = pd.DataFrame({'lagged': temp_lagged, 'price': merged['CL_F_Price']}).dropna()
        c = np.corrcoef(temp_df['lagged'], temp_df['price'])[0, 1]
        corrs.append(c)
        
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    # Time Series Overlay
    ax1.plot(df_clean['Date'], df_clean['CL_F_Price'], color='#26c6da', label='WTI Crude Oil Futures ($/bbl)')
    ax1_twin = ax1.twinx()
    ax1_twin.plot(df_clean['Date'], df_clean['Chemical_Plume_Lagged'], color='#ff9800', alpha=0.7, label='Chemical Plume (Lagged 2w)')
    ax1.set_title("GoM Chemical Plume (Lagged 2 Weeks) vs. Crude Oil Prices")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Crude Oil Price ($/bbl)")
    ax1_twin.set_ylabel("Plume Concentration Index")
    ax1.grid(True, linestyle='--', alpha=0.3)
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_twin.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    # Lead-Lag Curve
    ax2.plot(lags, corrs, color='#ef5350', linewidth=2)
    ax2.axvline(x=14, color='#ff6b6b', linestyle='--', label='Target Lead: 14 Days (2 Weeks)')
    ax2.set_title("Lead-Lag Correlation Analysis (Chemical Plume leading Crude Oil)")
    ax2.set_xlabel("Ocean Signal Lag (Days)")
    ax2.set_ylabel("Pearson Correlation Coefficient (r)")
    ax2.grid(True, linestyle='--', alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    plot_path = os.path.join(PLOTS_DIR, "test3_plume_oil.png")
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"Saved correlation diagnostic plot to {plot_path}")
    
    return r_lagged, sharpe, hit_rate

def main():
    print("=========================================================")
    print("          PROJECT NEPTUNE BACKTEST ENGINE                ")
    print("=========================================================")
    
    results = {}
    
    t1_results = run_test_1()
    if t1_results:
        results['Test 1 (ENSO vs Copper)'] = t1_results
        
    t2_results = run_test_2()
    if t2_results:
        results['Test 2 (Chlorophyll vs Tuna)'] = t2_results
        
    t3_results = run_test_3()
    if t3_results:
        results['Test 3 (Chemical Plume vs Oil)'] = t3_results
        
    print("\n=========================================================")
    print("                   BACKTEST SUMMARY                      ")
    print("=========================================================")
    print(f"{'Test Description':<32} | {'Pearson r':<9} | {'Sharpe':<6} | {'Hit Rate':<8} | {'Status':<5}")
    print("-" * 72)
    
    passing_tests = 0
    for test_name, (r, sharpe, hit_rate) in results.items():
        # Handle negative correlation logic for Test 2 (chlorophyll drop -> higher price)
        abs_r = abs(r)
        status = "PASS" if abs_r > 0.72 else "FAIL"
        if status == "PASS":
            passing_tests += 1
        print(f"{test_name:<32} | {r:>9.4f} | {sharpe:>6.2f} | {hit_rate:>8.2%} | {status:<5}")
        
    print("-" * 72)
    print(f"Total Passing Tests (r > 0.72): {passing_tests} / {len(results)}")
    
    if passing_tests >= 2:
        print("\nSUCCESS: Phase 0 Validation Target Met! Proved ocean correlation signal.")
        print("Ready to proceed to Phase 1 (Sign 1 paying client).")
    else:
        print("\nFAILURE: Did not achieve correlation r > 0.72 on at least 2 tests. Iterate models.")
    print("=========================================================")

if __name__ == "__main__":
    main()
