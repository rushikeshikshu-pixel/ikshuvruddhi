"""
scripts/train_tonnage_with_crushing_data.py
Trains and calibrates plot-level yield, standing tonnage, harvested cut tonnage,
and factory recovery against the 25 & 26 October 2026 ground-truth mill weighbridge slips.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MASTER_CSV = os.path.join(ROOT, 'data', 'output', 'all_unharvested_plots_oct2026_latest_satellite_register.csv')
CRUSH_CSV = os.path.join(ROOT, 'data', 'gangamai_crushing_25_26_oct2026_aggregated.csv')
DL_CSV = r"C:\Users\rishi\Downloads\Gangamai_29384_Plots_25Oct2026_Latest_Satellite_Register.csv"

print("1. Loading ground truth crushing data...")
df_crush = pd.read_csv(CRUSH_CSV, encoding='utf-8')
print(f"Crushing plots: {len(df_crush):,} | Total weight: {df_crush['crushed_tonnage_mt'].sum():,.2f} MT | Slips: {df_crush['crush_slips'].sum():,}")

print("2. Loading master satellite register...")
df = pd.read_csv(MASTER_CSV, low_memory=False, encoding='utf-8')
print(f"Master plots: {len(df):,}")

# Ensure clean Plot No integer
df['Plot No'] = pd.to_numeric(df['Plot No'], errors='coerce').fillna(-1).astype(int)
df_crush['DOCUMENT_NO'] = pd.to_numeric(df_crush['DOCUMENT_NO'], errors='coerce').fillna(-1).astype(int)

# Identify matched plots
matched_mask = df['Plot No'].isin(df_crush['DOCUMENT_NO'])
print(f"Matched directly in master register: {matched_mask.sum():,} plots")

# Merge crushing fields
crush_map = df_crush.set_index('DOCUMENT_NO')

# Add / update factory crushing columns
df['factory_crushed_tonnage_mt'] = df['Plot No'].map(crush_map['crushed_tonnage_mt']).fillna(0.0).round(3)
df['factory_crush_slips'] = df['Plot No'].map(crush_map['crush_slips']).fillna(0).astype(int)
df['factory_lab_recovery_pct'] = df['Plot No'].map(crush_map['crush_recovery_pct']).fillna(0.0).round(2)
df['factory_crush_dates'] = df['Plot No'].map(crush_map['crush_dates']).fillna('')

# Get baseline fields
area_ha = pd.to_numeric(df['registered_area_ha'], errors='coerce').fillna(df['Geodesic Walked Ha']).fillna(0.8)
prior_yield = pd.to_numeric(df['Yield (MT/Ha)'], errors='coerce').fillna(100.0)

# Calculate empirical yield multiplier per Circle / Shivar
matched_df = df[matched_mask].copy()
matched_crushed = matched_df['factory_crushed_tonnage_mt']
matched_area = area_ha[matched_mask]
matched_prior_yield = prior_yield[matched_mask]

# Circle / Village calibration multiplier with Bayesian shrinkage
village_col = 'Village' if 'Village' in df.columns else 'Circle / Gut'
circle_col = 'Circle / Gut' if 'Circle / Gut' in df.columns else 'Village'

circle_ratios = {}
for circle, grp in df[matched_mask].groupby(circle_col):
    actual_ton = grp['factory_crushed_tonnage_mt'].sum()
    # Expected tonnage on harvested area
    h_area = pd.to_numeric(grp['harvested_cane_area_ha'], errors='coerce').fillna(grp['Geodesic Walked Ha'] * 0.3)
    exp_ton = (h_area * pd.to_numeric(grp['Yield (MT/Ha)'], errors='coerce')).sum()
    if exp_ton > 0:
        raw_ratio = actual_ton / exp_ton
        # Bayesian shrinkage: shrink towards 1.0 based on sample size
        n = len(grp)
        shrunk_ratio = (n * raw_ratio + 15 * 1.0) / (n + 15)
        circle_ratios[circle] = float(np.clip(shrunk_ratio, 0.85, 1.30))

print(f"Calculated yield calibration multipliers for {len(circle_ratios)} circles.")
mean_circle_mult = np.mean(list(circle_ratios.values())) if circle_ratios else 1.05
print(f"Mean circle multiplier: {mean_circle_mult:.3f}")

# Apply yield calibration across all plots
calibrated_yield = prior_yield.copy()
for i, circle in enumerate(df[circle_col]):
    mult = circle_ratios.get(circle, mean_circle_mult)
    calibrated_yield.iloc[i] = np.round(prior_yield.iloc[i] * mult, 1)

# For matched plots that were crushed:
# If crushed tonnage exceeds harvested tonnage, we calibrate yield directly on observed weight
for idx in df[matched_mask].index:
    crushed = df.loc[idx, 'factory_crushed_tonnage_mt']
    p_area = area_ha.loc[idx]
    # If crushed weight is higher than total expected, adjust yield
    if crushed > (p_area * calibrated_yield.loc[idx]):
        calibrated_yield.loc[idx] = np.round(crushed / p_area * 1.05, 1)

df['Yield (MT/Ha)'] = calibrated_yield
df['calibrated_yield_mt_ha'] = calibrated_yield

print("3. Reconciling Standing Tonnage and Harvested Cut Tonnage...")
# Total plot tonnage
total_plot_tonnage = np.round(area_ha * calibrated_yield, 1)

# Current harvest progress from satellite canopy retention
curr_ndvi = pd.to_numeric(df['optical_ndvi'], errors='coerce').fillna(0.60)
prev_ndvi = pd.to_numeric(df['previous_optical_ndvi'], errors='coerce').fillna(0.65)
retention = np.clip((curr_ndvi - 0.18) / (np.maximum(prev_ndvi, 0.50) - 0.18), 0.05, 1.00)

# Baseline satellite cut tonnage
sat_cut_tonnage = np.round(area_ha * (1.0 - retention) * calibrated_yield, 1)

# Ground truth reconciliation:
# Harvested Cut Tonnage is MAX of satellite cut tonnage and actual factory weighbridge crushed tonnage
harvested_cut_tonnage = np.maximum(sat_cut_tonnage, df['factory_crushed_tonnage_mt'])

# Cap harvested cut tonnage at total plot tonnage
harvested_cut_tonnage = np.minimum(harvested_cut_tonnage, total_plot_tonnage)

# Standing millable tonnage is remaining cane
standing_millable_tonnage = np.round(np.maximum(0.0, total_plot_tonnage - harvested_cut_tonnage), 1)

# Re-derive harvested area and detected standing cane area
harvested_area_ha = np.round(np.where(calibrated_yield > 0, harvested_cut_tonnage / calibrated_yield, 0.0), 4)
harvested_area_ha = np.minimum(harvested_area_ha, area_ha)
detected_standing_area_ha = np.round(np.maximum(0.0, area_ha - harvested_area_ha), 4)

harvest_progress_pct = np.round(np.where(area_ha > 0, (harvested_area_ha / area_ha) * 100.0, 0.0), 1)
canopy_occupancy = np.round(np.where(area_ha > 0, detected_standing_area_ha / area_ha, 0.0), 3)

df['Standing Millable Tonnage (MT)'] = standing_millable_tonnage
df['Harvested Cut Tonnage (MT)'] = harvested_cut_tonnage
df['Total Estimated Tonnage (MT)'] = total_plot_tonnage
df['detected_cane_area_ha'] = detected_standing_area_ha
df['harvested_cane_area_ha'] = harvested_area_ha
df['harvest_progress_pct'] = harvest_progress_pct
df['canopy_occupancy_fraction'] = canopy_occupancy

# Update factory lab recovery into master recovery for crushed plots
for idx in df[matched_mask].index:
    rec = df.loc[idx, 'factory_lab_recovery_pct']
    if rec > 0:
        df.loc[idx, 'predicted_recovery_pct'] = rec
        df.loc[idx, 'Early Season Recovery (%)'] = rec
        # Calculate CCS and Pol / Brix commensurate with lab recovery
        ccs = np.round(rec / 0.754, 2)
        df.loc[idx, 'predicted_ccs_pct'] = ccs
        df.loc[idx, 'Updated CCS on Cane (%)'] = ccs

# Update harvest maturity tiers
tiers = []
for idx in df.index:
    h = df.loc[idx, 'harvest_progress_pct']
    crushed = df.loc[idx, 'factory_crushed_tonnage_mt']
    standing = df.loc[idx, 'Standing Millable Tonnage (MT)']
    
    if standing <= 1.0 and crushed > 0:
        tiers.append("Harvest Complete (Delivered to Mill)")
    elif crushed > 0:
        tiers.append(f"Active Crushing ({crushed:.1f} MT Delivered | {standing:.1f} MT Standing)")
    elif h >= 85.0:
        tiers.append("Tier 1: Harvest Nearly Complete (85-95% Cut)")
    elif h >= 20.0:
        tiers.append(f"Tier 1: Partial Harvest Active ({h:.0f}% Cut)")
    else:
        ccs = df.loc[idx, 'predicted_ccs_pct']
        if ccs >= 10.20:
            tiers.append("Tier 1: Peak Ripening (Harvest Now)")
        elif ccs >= 9.20:
            tiers.append("Tier 2: Mid-Maturity (Harvest in 2-3 Wks)")
        else:
            tiers.append("Tier 3: Immature (Hold 4-6 Wks)")

df['harvest_maturity_tier'] = tiers

print("\n" + "="*65)
print("CRUSHING DATA TRAINING & CALIBRATION SUMMARY (25-26 OCT 2026)")
print("="*65)
print(f"Total Plots: {len(df):,}")
print(f"Total Crushed Plots Matched: {matched_mask.sum():,} plots")
print(f"Actual Factory Delivered Cane: {df['factory_crushed_tonnage_mt'].sum():,.2f} MT")
print(f"Actual Factory Weighbridge Slips: {df['factory_crush_slips'].sum():,}")
print(f"Total Standing Millable Tonnage: {df['Standing Millable Tonnage (MT)'].sum():,.1f} MT")
print(f"Total Harvested Cut Tonnage: {df['Harvested Cut Tonnage (MT)'].sum():,.1f} MT")
print(f"Total Biomass (Standing + Harvested): {(df['Standing Millable Tonnage (MT)'] + df['Harvested Cut Tonnage (MT)']).sum():,.1f} MT")
print(f"Mean Calibrated Yield: {df['Yield (MT/Ha)'].mean():.2f} MT/Ha")
print(f"Plots with Active Mill Deliveries: {(df['factory_crushed_tonnage_mt'] > 0).sum():,} plots")
print("="*65 + "\n")

# Save master CSV
print("4. Saving calibrated master CSV...")
df.to_csv(MASTER_CSV, index=False, encoding='utf-8')
df.to_csv(DL_CSV, index=False, encoding='utf-8')
print("Successfully saved to master CSV and Downloads folder!")

# Update javascript web files
print("5. Updating web and cloudflare_public static JS...")
sample_plots = df.fillna('').head(3500).to_dict(orient='records')
js_content = "window.MILL_CALIBRATED_PLOTS = " + json.dumps(sample_plots, default=str) + ";\n"

for js_path in [
    os.path.join(ROOT, 'web', 'mill_calibrated_plots.js'),
    os.path.join(ROOT, 'cloudflare_public', 'mill_calibrated_plots.js')
]:
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)
print("Updated web/mill_calibrated_plots.js and cloudflare_public/mill_calibrated_plots.js")
