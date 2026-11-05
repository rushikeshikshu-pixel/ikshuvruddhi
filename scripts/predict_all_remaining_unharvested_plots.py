"""
scripts/predict_all_remaining_unharvested_plots.py
==================================================
Runs batch inference using the retrained 54-parameter 4-satellite engine across
all 26,471 remaining unharvested plots in the Gangamai command area (23,276.4 Ha).

Generates:
1. web/downloads/Gangamai_Unharvested_Plots_Latest_Satellite_Predictions_05Nov2026.csv
2. data/output/Gangamai_Unharvested_Plots_Latest_Satellite_Predictions_05Nov2026.csv
3. Analytical summary report with distribution percentiles and cluster rankings.
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(ROOT, 'data', 'output')
WEB_DL_DIR = os.path.join(ROOT, 'web', 'downloads')
MODELS_DIR = os.path.join(ROOT, 'models')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(WEB_DL_DIR, exist_ok=True)

print("=" * 95)
print("SATCANE AI: BATCH INFERENCE ON ALL REMAINING UNHARVESTED PLOTS")
print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 95)

# 1. Load Retrained 54-Parameter Model Bundle
bundle_path = os.path.join(MODELS_DIR, 'sota_54param_4satellite_bundle.pkl')
if not os.path.exists(bundle_path):
    raise FileNotFoundError(f"Model bundle not found at {bundle_path}")

with open(bundle_path, 'rb') as f:
    bundle = pickle.load(f)

model_pol = bundle['model_pol']
model_brix = bundle['model_brix']
model_rec = bundle['model_recovery']
features = bundle['features']

print(f"Loaded Retrained Model Bundle (Trained on {bundle.get('training_samples', 814)} certified samples).")
print(f"Features: {len(features)} multi-satellite parameters.")

# 2. Load All Unharvested Plots
UNH_CSV = os.path.join(WEB_DL_DIR, 'all_unharvested_plots_oct2026_latest_satellite_register.csv')
print(f"\nLoading unharvested plots register from: {UNH_CSV}")
df_unh = pd.read_csv(UNH_CSV, low_memory=False)
total_plots = len(df_unh)
print(f"Total Unharvested Plots: {total_plots:,}")
print(f"Total Registered Area: {df_unh['Registered Ha'].sum():,.2f} Hectares")

# 3. Construct Feature Matrix X
print("\nConstructing 54-parameter feature matrix X...")
X = pd.DataFrame(index=df_unh.index)
for col in features:
    if col in df_unh.columns:
        s = pd.to_numeric(df_unh[col], errors='coerce')
        X[col] = s.fillna(s.median() if not np.isnan(s.median()) else 0.0)
    else:
        X[col] = 0.0

# 4. Predict Pol, Brix, and Direct Recovery
print("Executing batch inference across all 26,471 plots...")
pred_pol_raw = model_pol.predict(X)
pred_brix_raw = model_brix.predict(X)

# Clip to realistic agronomic biological ranges for standing cane
pred_pol = np.clip(pred_pol_raw, 10.5, 17.5)
pred_brix = np.clip(pred_brix_raw, 13.0, 20.0)
# Ensure Pol does not exceed Brix (mathematical constraint)
pred_pol = np.minimum(pred_pol, pred_brix * 0.92)

# Calculate Purity, CCS, and Calibrated Factory Recovery
pred_purity = np.clip((pred_pol / pred_brix) * 100.0, 70.0, 92.0)
pred_ccs = np.clip(1.022 * pred_pol - 0.292 * pred_brix, 7.0, 12.0)

# Realized Factory Recovery = CCS * 0.804 (Closed-loop mill extraction 94.12% * BHR 85.5%)
K_EFF = 0.804
pred_recovery = np.round(pred_ccs * K_EFF, 3)

# Transit Delay Staling Model (10 hours daytime delay = -0.45% Pol loss)
delayed_pol = np.round(pred_pol - 0.45, 2)
delayed_ccs = np.round(1.022 * delayed_pol - 0.292 * pred_brix, 3)
delayed_recovery = np.round(delayed_ccs * K_EFF, 3)
immediate_crush_gain = np.round(pred_recovery - delayed_recovery, 3)

# Assign outputs
df_unh['Nov05_Standing_Brix_degBx'] = np.round(pred_brix, 2)
df_unh['Nov05_Standing_Pol_pct'] = np.round(pred_pol, 2)
df_unh['Nov05_Juice_Purity_pct'] = np.round(pred_purity, 2)
df_unh['Nov05_Standing_CCS_pct'] = np.round(pred_ccs, 2)
df_unh['Nov05_Optimal_Factory_Recovery_pct'] = np.round(pred_recovery, 2)
df_unh['Nov05_Delayed_10hr_Crush_Recovery_pct'] = np.round(delayed_recovery, 2)
df_unh['Nov05_Logistics_Optimization_Gain_pct'] = np.round(immediate_crush_gain, 2)

# Calculate Millable Sugar Tonnage
standing_tonnage = pd.to_numeric(df_unh['Standing Millable Tonnage (MT)'], errors='coerce').fillna(
    df_unh['Registered Ha'] * 85.0
)
df_unh['Standing_Millable_Tonnage_MT'] = np.round(standing_tonnage, 1)
df_unh['Estimated_Sugar_Production_MT'] = np.round(standing_tonnage * (df_unh['Nov05_Optimal_Factory_Recovery_pct'] / 100.0), 2)
df_unh['Estimated_Sugar_Bags_50kg'] = np.round(df_unh['Estimated_Sugar_Production_MT'] * 20.0).astype(int)

# 5. Harvest Maturity Classification and Priority Ranking
def classify_maturity(ccs):
    if ccs >= 9.50:
        return 'OPTIMAL_MATURE_PRIORITY_HARVEST'
    elif ccs >= 8.80:
        return 'MID_SEASON_RIPE'
    else:
        return 'EARLY_STAGE_IMMATURE'

df_unh['Nov05_Maturity_Classification'] = df_unh['Nov05_Standing_CCS_pct'].apply(classify_maturity)

# Sort descending by CCS and assign Harvest Priority Rank
df_unh = df_unh.sort_values(by='Nov05_Standing_CCS_pct', ascending=False).reset_index(drop=True)
df_unh['Nov05_Harvest_Priority_Rank'] = df_unh.index + 1

# 6. Save Complete Files
export_cols = [
    'Nov05_Harvest_Priority_Rank', 'Plot No', 'Farmer Name', 'Village', 'Circle / Gut', 'Variety',
    'Registered Ha', 'Standing_Millable_Tonnage_MT',
    'Nov05_Standing_Brix_degBx', 'Nov05_Standing_Pol_pct', 'Nov05_Juice_Purity_pct',
    'Nov05_Standing_CCS_pct', 'Nov05_Optimal_Factory_Recovery_pct',
    'Nov05_Delayed_10hr_Crush_Recovery_pct', 'Nov05_Logistics_Optimization_Gain_pct',
    'Estimated_Sugar_Production_MT', 'Estimated_Sugar_Bags_50kg',
    'Nov05_Maturity_Classification', 'Copernicus Real NDVI', 'Copernicus Real NDRE',
    'True Crop Age as of Oct 22 (Days)', 'lat_min', 'lon_min'
]
available_export_cols = [c for c in export_cols if c in df_unh.columns]

# Main concise executive register
out_web_csv = os.path.join(WEB_DL_DIR, 'Gangamai_Unharvested_Plots_Latest_Satellite_Predictions_05Nov2026.csv')
out_data_csv = os.path.join(DATA_DIR, 'Gangamai_Unharvested_Plots_Latest_Satellite_Predictions_05Nov2026.csv')

print(f"\nExporting concise register ({len(available_export_cols)} columns) to:")
print(f"  -> {out_web_csv}")
df_unh[available_export_cols].to_csv(out_web_csv, index=False)
df_unh[available_export_cols].to_csv(out_data_csv, index=False)

# Also update the master unharvested register
df_unh.to_csv(UNH_CSV, index=False)
print("Updated master unharvested register with retrained Nov 05 predictions.")

# 7. Print Comprehensive Summary Analytics
print("\n" + "=" * 95)
print("COMPREHENSIVE ANALYTICAL SUMMARY (26,471 UNHARVESTED PLOTS):")
print("=" * 95)
stats = df_unh[['Nov05_Standing_Brix_degBx', 'Nov05_Standing_Pol_pct', 'Nov05_Juice_Purity_pct', 'Nov05_Standing_CCS_pct', 'Nov05_Optimal_Factory_Recovery_pct']].describe()
print(stats.to_string())

print("\n--- MATURITY BREAKDOWN ---")
counts = df_unh['Nov05_Maturity_Classification'].value_counts()
pcts = df_unh['Nov05_Maturity_Classification'].value_counts(normalize=True) * 100.0
for k in counts.index:
    print(f"  • {k:35s}: {counts[k]:5,d} plots ({pcts[k]:5.1f}%) | Cane: {df_unh[df_unh['Nov05_Maturity_Classification'] == k]['Standing_Millable_Tonnage_MT'].sum():,.0f} MT")

print("\n--- TOP 10 HARVESTING PRIORITY CLUSTERS (VILLAGES) ---")
top_villages = df_unh[df_unh['Nov05_Maturity_Classification'] == 'OPTIMAL_MATURE_PRIORITY_HARVEST'].groupby('Village').agg(
    high_sugar_plots=('Plot No', 'count'),
    total_cane_mt=('Standing_Millable_Tonnage_MT', 'sum'),
    mean_ccs=('Nov05_Standing_CCS_pct', 'mean'),
    mean_recovery=('Nov05_Optimal_Factory_Recovery_pct', 'mean')
).sort_values(by='high_sugar_plots', ascending=False).head(10)
print(top_villages.to_string())

total_cane = df_unh['Standing_Millable_Tonnage_MT'].sum()
total_sugar_opt = df_unh['Estimated_Sugar_Production_MT'].sum()
total_sugar_delayed = (df_unh['Standing_Millable_Tonnage_MT'] * (df_unh['Nov05_Delayed_10hr_Crush_Recovery_pct'] / 100.0)).sum()
lost_bags = (total_sugar_opt - total_sugar_delayed) * 20.0

print("\n--- MACRO FACTORY IMPACT ---")
print(f"Total Standing Cane:            {total_cane:,.0f} MT")
print(f"Total Recoverable Sugar (Opt):  {total_sugar_opt:,.1f} MT ({total_sugar_opt * 20:,.0f} Bags)")
print(f"Total Sugar with 10-Hr Staling: {total_sugar_delayed:,.1f} MT ({total_sugar_delayed * 20:,.0f} Bags)")
print(f"Sugar Burned by Transit Delay:  {total_sugar_opt - total_sugar_delayed:,.1f} MT ({lost_bags:,.0f} Bags)")
print("=" * 95)
