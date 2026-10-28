"""
scripts/deploy_hierarchical_dual_scale.py
Executes and deploys the Hierarchical Dual-Head Architecture across all 29,384 plots.
Integrates:
  - Heteroscedastic Aleatoric Weighbridge Noise Filtering
  - Head 1: Relative Todni Harvest Ripening Ranking (0-100 Score & Rank)
  - Head 2: Factory Mass Conservation Balance (Scientific Kf = 0.814)
  - Spatial Kriging Neighbor Propagation across all Circles
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from ml.hierarchical_dual_scale_engine import HierarchicalDualScaleEngine

MASTER_CSV = os.path.join(ROOT, 'data', 'output', 'all_unharvested_plots_oct2026_latest_satellite_register.csv')
CRUSH_EXCEL = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
DL_CSV = r"C:\Users\rishi\Downloads\Gangamai_29384_Plots_25Oct2026_Latest_Satellite_Register.csv"

print("1. Loading raw crushing sheets & computing Aleatoric Noise...")
xl = pd.ExcelFile(CRUSH_EXCEL)
df_crush_raw = pd.concat([xl.parse("25.10.2026"), xl.parse("26.10.2026")], ignore_index=True)
df_crush_raw['DOCUMENT_NO'] = pd.to_numeric(df_crush_raw['DOCUMENT_NO'], errors='coerce')
df_crush_raw = df_crush_raw.dropna(subset=['DOCUMENT_NO'])
df_crush_raw['DOCUMENT_NO'] = df_crush_raw['DOCUMENT_NO'].astype(int)

engine = HierarchicalDualScaleEngine(kf=0.814, base_aleatoric=0.34)
df_crush_raw['slip_noise_sigma'] = engine.compute_aleatoric_noise(df_crush_raw)

# Aggregate per plot with noise precision
df_crush_agg = df_crush_raw.groupby('DOCUMENT_NO').agg(
    crushed_tonnage_mt=('NET_WT', 'sum'),
    crush_slips=('NET_WT', 'count'),
    # Tonnage-weighted Pol in Juice
    crush_recovery_pct=('RECOVERY_PER', lambda r: (r * df_crush_raw.loc[r.index, 'NET_WT']).sum() / df_crush_raw.loc[r.index, 'NET_WT'].sum()),
    weighbridge_noise_sigma=('slip_noise_sigma', 'mean'),
    crush_dates=('WSLIP_DATE', lambda d: ', '.join(sorted(list(set(d.astype(str)))))),
    shivar_name=('SHIVAR_NAME', 'first')
).reset_index()

print(f"Aggregated {len(df_crush_agg)} unique plots from {len(df_crush_raw)} slips.")
print(f"Mean Estimated Weighbridge Noise: ±{df_crush_agg['weighbridge_noise_sigma'].mean():.3f}%")

print("2. Loading Master Register...")
df_master = pd.read_csv(MASTER_CSV, low_memory=False, encoding='utf-8')
print(f"Loaded master register with {len(df_master):,} parcels.")

# Run Hierarchical Dual-Scale Engine
df_calibrated = engine.calibrate_dual_scale(df_master, df_crush_agg)

# Save deliverables
print("5. Exporting updated datasets to Master CSV and Downloads...")
df_calibrated.to_csv(MASTER_CSV, index=False, encoding='utf-8')
df_calibrated.to_csv(DL_CSV, index=False, encoding='utf-8')
print(f"Saved to {MASTER_CSV} and {DL_CSV}")

# Update web JS files
print("6. Updating web and cloudflare_public static JS...")
sample_plots = df_calibrated.fillna('').head(3500).to_dict(orient='records')
js_content = "window.MILL_CALIBRATED_PLOTS = " + json.dumps(sample_plots, default=str) + ";\n"

for js_path in [
    os.path.join(ROOT, 'web', 'mill_calibrated_plots.js'),
    os.path.join(ROOT, 'cloudflare_public', 'mill_calibrated_plots.js')
]:
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)

print("Updated web/mill_calibrated_plots.js and cloudflare_public/mill_calibrated_plots.js")
print("SUCCESS: Hierarchical Dual-Scale Engine successfully deployed!")
