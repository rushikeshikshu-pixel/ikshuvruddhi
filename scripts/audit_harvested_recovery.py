# -*- coding: utf-8 -*-
import sys
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

df_harv = pd.read_csv('data/output/all_harvested_plots_oct2026_register.csv', low_memory=False)
df_unh = pd.read_csv('data/output/all_unharvested_plots_oct2026_latest_satellite_register.csv', low_memory=False)

print("=" * 80)
print("GANGAMAI SUGAR MILL - HARVESTED PLOTS & RECOVERY AUDIT CROSSCHECK")
print("=" * 80)

total_harv_plots = len(df_harv)
total_unh_plots = len(df_unh)
total_command_plots = total_harv_plots + total_unh_plots

total_harv_ton = df_harv['Harvested Cut Tonnage (MT)'].sum()
total_harv_ha = df_harv['harvested_cane_area_ha'].sum() if 'harvested_cane_area_ha' in df_harv.columns else df_harv['Registered Ha'].sum()
total_harv_acres = df_harv['Geodesic Walked Acres'].sum() if 'Geodesic Walked Acres' in df_harv.columns else total_harv_ha * 2.47105

print(f"1. Command Overview:")
print(f"   • Total Enrolled Command Area Plots : {total_command_plots:,}")
print(f"   • Total Harvested / Crushed Plots    : {total_harv_plots:,} ({total_harv_plots/total_command_plots*100:.1f}%)")
print(f"   • Total Remaining Standing Plots    : {total_unh_plots:,} ({total_unh_plots/total_command_plots*100:.1f}%)")
print(f"   • Total Harvested Area              : {total_harv_ha:,.2f} Ha ({total_harv_acres:,.2f} Acres)")
print(f"   • Total Cumulative Crushed Tonnage  : {total_harv_ton:,.1f} MT")
print(f"   • Average Tonnage per Plot          : {total_harv_ton/total_harv_plots:.1f} MT/plot")

print("\n2. Breakdown by Operational Harvest Batch:")
for batch, grp in df_harv.groupby('Harvest Batch'):
    ton = grp['Harvested Cut Tonnage (MT)'].sum()
    pct_ton = ton / total_harv_ton * 100
    mean_pot = grp['Potential Factory Recovery (%)'].mean()
    mean_act = grp['Actual Realized Recovery (%)'].mean()
    print(f"   • {batch:<42} : {len(grp):>5,} plots | {ton:>9,.1f} MT ({pct_ton:>4.1f}%) | Field Pot: {mean_pot:.2f}% | Realized: {mean_act:.2f}%")

print("\n3. Recovery Cross-Check & Cumulative Math:")
# Let's inspect the actual realized recovery across the crushed cane
weighted_actual = (df_harv['Actual Realized Recovery (%)'] * df_harv['Harvested Cut Tonnage (MT)']).sum() / total_harv_ton
weighted_pot = (df_harv['Potential Factory Recovery (%)'] * df_harv['Harvested Cut Tonnage (MT)']).sum() / total_harv_ton

print(f"   • Total Sugar Produced (Calculated)  : {(df_harv['Actual Realized Recovery (%)'] * df_harv['Harvested Cut Tonnage (MT)'] / 100.0).sum():,.1f} MT")
print(f"   • Weighted Actual Realized Recovery  : {weighted_actual:.2f}%")
print(f"   • Weighted Field Potential Recovery  : {weighted_pot:.2f}%")
print(f"   • Cumulative Transit / House Loss    : {weighted_actual - weighted_pot:.2f}%")

print("\n4. Factory Stated Daily Progression Cross-Check:")
print(f"   • Opening Crush to 31 Oct Avg       : ~7.60% - 7.68%")
print(f"   • 01 Nov 2026 Daily Realized        : 8.21% (Crushed ~5,000 MT)")
print(f"   • 02 Nov 2026 Daily Realized        : 8.31% (Crushed ~5,000 MT) -> pulls cumulative to 7.74%")
print(f"   • 03 Nov 2026 Daily Realized        : 8.44% (Crushed ~2,500-3,500 MT) -> pulls cumulative to 7.75%")
print(f"   • Cumulative Season Average to date : 7.74% (Reported by Mill Weighbridge/Lab)")
print(f"   • Model Unharvested Standing Area   : {df_unh['Potential Factory Recovery (%)'].mean():.2f}% (Calibrated baseline)")

print("=" * 80)
