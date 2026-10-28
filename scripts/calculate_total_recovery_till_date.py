import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# 1. 25-26 Oct Actual Weighbridge Deliveries
excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
df_crush = pd.concat([xl.parse("25.10.2026"), xl.parse("26.10.2026")], ignore_index=True)
df_crush['NET_WT'] = pd.to_numeric(df_crush['NET_WT'], errors='coerce')
df_crush['POL_JUICE'] = pd.to_numeric(df_crush['RECOVERY_PER'], errors='coerce')
df_crush = df_crush.dropna(subset=['NET_WT', 'POL_JUICE'])

df_crush['BRIX'] = np.round(df_crush['POL_JUICE'] / 0.85, 2)
df_crush['CCS'] = np.round(1.022 * df_crush['POL_JUICE'] - 0.292 * df_crush['BRIX'], 2)
df_crush['EARLY_RECOVERY'] = np.round(df_crush['CCS'] * 0.754, 2)
df_crush['PEAK_RECOVERY'] = np.round(df_crush['CCS'] * 0.820, 2)

# Sugar produced in Metric Tonnes = Tonnage * (Recovery % / 100)
df_crush['SUGAR_MT_EARLY'] = df_crush['NET_WT'] * (df_crush['EARLY_RECOVERY'] / 100.0)
df_crush['SUGAR_MT_PEAK'] = df_crush['NET_WT'] * (df_crush['PEAK_RECOVERY'] / 100.0)

crush_cane_total = df_crush['NET_WT'].sum()
crush_sugar_early = df_crush['SUGAR_MT_EARLY'].sum()
crush_sugar_peak = df_crush['SUGAR_MT_PEAK'].sum()
weighted_crush_recovery = (crush_sugar_early / crush_cane_total) * 100.0

print("--- 1. WEIGHBRIDGE DELIVERIES (25-26 OCT 2026) ---")
print(f"Total Crushed Cane Delivered:    {crush_cane_total:,.2f} MT")
print(f"Weighted Average Sugar Recovery: {weighted_crush_recovery:.2f}%")
print(f"Total Sugar Recovered (Oct/Nov): {crush_sugar_early:,.2f} MT (~{crush_sugar_early*10:,.0f} quintal bags)")
print(f"Total Sugar Potential (Peak):    {crush_sugar_peak:,.2f} MT (~{crush_sugar_peak*10:,.0f} quintal bags)")

# 2. Master Register (Command Area Harvested Biomass till date)
master_csv = 'data/output/all_unharvested_plots_oct2026_latest_satellite_register.csv'
df_master = pd.read_csv(master_csv, low_memory=False, encoding='utf-8')

h_tonnage = pd.to_numeric(df_master['Harvested Cut Tonnage (MT)'], errors='coerce').fillna(0.0)
h_rec = pd.to_numeric(df_master['Early Season Recovery (%)'], errors='coerce').fillna(
    pd.to_numeric(df_master['predicted_recovery_pct'], errors='coerce')
).fillna(7.0)

# Plots with harvesting activity (harvest_progress > 5% or crushed > 0)
h_prog = pd.to_numeric(df_master['harvest_progress_pct'], errors='coerce').fillna(0.0)
has_harvest = (h_prog >= 5.0) | (df_master['factory_crushed_tonnage_mt'] > 0) | (h_tonnage > 0)

tot_h_tonnage = h_tonnage.sum()
tot_h_sugar = (h_tonnage * (h_rec / 100.0)).sum()
tot_h_weighted_rec = (tot_h_sugar / tot_h_tonnage) * 100.0 if tot_h_tonnage > 0 else 0.0

print("\n--- 2. ENTIRE COMMAND AREA HARVESTED TILL DATE (SATELLITE + GATE RECEIPTS) ---")
print(f"Total Plots with Harvest Activity: {has_harvest.sum():,} plots")
print(f"Total Harvested Cut Cane Tonnage:  {tot_h_tonnage:,.1f} MT")
print(f"Average Harvested Cane Recovery:   {tot_h_weighted_rec:.2f}%")
print(f"Total Sugar Recovered / Realized:  {tot_h_sugar:,.1f} MT (~{tot_h_sugar*10:,.0f} quintals)")

# Check 410 confirmed archived plots if available
print("\n--- 3. COMPARISON ---")
print(f"Factory Gate Slips Crushed (25-26 Oct): {crush_cane_total:,.2f} MT cane -> {crush_sugar_early:,.2f} MT sugar @ {weighted_crush_recovery:.2f}%")
print(f"Total Field Cut Biomass Detected:      {tot_h_tonnage:,.2f} MT cane -> {tot_h_sugar:,.2f} MT sugar @ {tot_h_weighted_rec:.2f}%")
