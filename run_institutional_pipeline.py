import subprocess
import os
import sys
from datetime import datetime

def run_script(script_name):
    print(f"\n>>> Executing {script_name}...")
    result = subprocess.run([sys.executable, script_name], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
        return True
    else:
        print(f"Error executing {script_name}:")
        print(result.stderr)
        return False

def main():
    print("=========================================================")
    print("      PROJECT NEPTUNE INSTITUTIONAL QUANT PIPELINE       ")
    print("=========================================================")
    
    start_time = datetime.now()
    
    # Step 1: Run Grid Search Parameter Optimization
    if not run_script("quant_optimizer.py"):
        print("Pipeline aborted at Step 1 (Optimization).")
        return
        
    # Step 2: Run Econometric Tests (Stationarity & Granger Causality)
    if not run_script("quant_econometrics.py"):
        print("Pipeline aborted at Step 2 (Econometrics).")
        return
        
    # Step 3: Package 20-Year Dataset for the Dashboard
    if not run_script("convert_csv_to_js.py"):
        print("Pipeline aborted at Step 3 (JS conversion).")
        return
        
    elapsed = (datetime.now() - start_time).total_seconds()
    print("=========================================================")
    print(f"Pipeline executed successfully in {elapsed:.2f} seconds!")
    print("All outputs generated:")
    print("  * optimized_parameters.json")
    print("  * quant_research_report.md")
    print("  * data-store.js (20-year browser database)")
    print("=========================================================")

if __name__ == "__main__":
    main()
