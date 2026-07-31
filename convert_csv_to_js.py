import os
import pandas as pd
import json

DATA_DIR = "data"
OUTPUT_FILE = "data-store.js"

def main():
    print("Converting CSV datasets to JavaScript data store...")
    
    datasets = {
        "sst": "noaa_sst_processed.csv",
        "copper": "HG_F_processed.csv",
        "oil": "CL_F_processed.csv",
        "chlorophyll": "chlorophyll_processed.csv",
        "tuna": "tuna_processed.csv",
        "plume": "chemical_plume_processed.csv"
    }
    
    js_data = {}
    
    for key, filename in datasets.items():
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            df = pd.read_csv(path)
            # Ensure Date is string format for JS parsing
            df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
            
            # Identify the value column (non-Date column)
            val_col = [col for col in df.columns if col != 'Date'][0]
            
            # Convert to list of dicts: [{'date': '2021-01-01', 'val': 0.12}, ...]
            records = []
            for _, row in df.iterrows():
                records.append({
                    "date": row['Date'],
                    "val": float(row[val_col]) if not pd.isna(row[val_col]) else 0.0
                })
            js_data[key] = records
            print(f"Loaded {len(records)} records for {key} ({filename})")
        else:
            print(f"Warning: {filename} not found in data directory.")
            
    # Write as a JavaScript variable file
    js_content = f"// Deepstream - Pre-cached Historical Datasets (2021-2026)\n"
    js_content += f"const NEPTUNE_DATA_STORE = {json.dumps(js_data, indent=2)};\n"
    
    with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
        f.write(js_content)
        
    print(f"Successfully generated {OUTPUT_FILE}!")

if __name__ == "__main__":
    main()
