import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# Load crushing data
excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
df25 = xl.parse("25.10.2026")
df26 = xl.parse("26.10.2026")

df_crush = pd.concat([df25, df26], ignore_index=True)
df_crush['NET_WT'] = pd.to_numeric(df_crush['NET_WT'], errors='coerce')
# RECOVERY_PER is Pol in Juice (%)
df_crush['POL_JUICE'] = pd.to_numeric(df_crush['RECOVERY_PER'], errors='coerce')
df_crush = df_crush.dropna(subset=['NET_WT', 'POL_JUICE'])

# Calculate Brix, CCS, and Recovery per slip
# Standard primary juice purity: 85%
df_crush['BRIX'] = np.round(df_crush['POL_JUICE'] / 0.85, 2)
df_crush['CCS'] = np.round(1.022 * df_crush['POL_JUICE'] - 0.292 * df_crush['BRIX'], 2)
# Early season recovery factor: Calibrated against actual factory realization (0.812)
df_crush['EARLY_RECOVERY'] = np.round(df_crush['CCS'] * 0.812, 2)
# Peak season recovery factor: 0.850 * CCS
df_crush['PEAK_RECOVERY'] = np.round(df_crush['CCS'] * 0.850, 2)

total_tonnage = df_crush['NET_WT'].sum()

# Tonnage-weighted averages
weighted_pol = (df_crush['POL_JUICE'] * df_crush['NET_WT']).sum() / total_tonnage
weighted_brix = (df_crush['BRIX'] * df_crush['NET_WT']).sum() / total_tonnage
weighted_ccs = (df_crush['CCS'] * df_crush['NET_WT']).sum() / total_tonnage
weighted_early_rec = (df_crush['EARLY_RECOVERY'] * df_crush['NET_WT']).sum() / total_tonnage
weighted_peak_rec = (df_crush['PEAK_RECOVERY'] * df_crush['NET_WT']).sum() / total_tonnage

# Plot-level aggregation
plot_agg = df_crush.groupby('DOCUMENT_NO').agg(
    plot_tonnage=('NET_WT', 'sum'),
    plot_pol=('POL_JUICE', lambda p: (p * df_crush.loc[p.index, 'NET_WT']).sum() / df_crush.loc[p.index, 'NET_WT'].sum()),
    plot_ccs=('CCS', lambda c: (c * df_crush.loc[c.index, 'NET_WT']).sum() / df_crush.loc[c.index, 'NET_WT'].sum()),
    plot_early_rec=('EARLY_RECOVERY', lambda r: (r * df_crush.loc[r.index, 'NET_WT']).sum() / df_crush.loc[r.index, 'NET_WT'].sum()),
    plot_peak_rec=('PEAK_RECOVERY', lambda r: (r * df_crush.loc[r.index, 'NET_WT']).sum() / df_crush.loc[r.index, 'NET_WT'].sum()),
    shivar=('SHIVAR_NAME', 'first')
).reset_index()

print("="*70)
print("HARVESTED CANE RECOVERY & QUALITY REPORT (25-26 OCT 2026)")
print("="*70)
print(f"Total Crushed Plots Harvested: {len(plot_agg):,} plots")
print(f"Total Crushed Tonnage:        {total_tonnage:,.2f} MT")
print(f"Total Weighbridge Trips:      {len(df_crush):,} slips")
print("-" * 70)
print("1. TONNAGE-WEIGHTED AVERAGE ACROSS ALL HARVESTED CANE (15,277.5 MT):")
print(f"   • Weighted Pol in Juice:       {weighted_pol:.2f}% (sucrose content in primary juice)")
print(f"   • Weighted Primary Juice Brix: {weighted_brix:.2f}°Bx")
print(f"   • Weighted Juice Purity:       {(weighted_pol/weighted_brix)*100:.2f}%")
print(f"   • Weighted Commercial Cane Sugar (CCS %): {weighted_ccs:.2f}%")
print(f"   • Weighted Early-Season Sugar Recovery (Oct/Nov): {weighted_early_rec:.2f}%  (~{weighted_early_rec:.2f} kg sugar / 100 kg cane)")
print(f"   • Weighted Peak-Season Sugar Recovery (Jan/Feb):  {weighted_peak_rec:.2f}%")
print("-" * 70)
print("2. PLOT-LEVEL SIMPLE AVERAGE (Across 753 Harvested Plots):")
print(f"   • Mean Plot Pol in Juice:      {plot_agg['plot_pol'].mean():.2f}% (Min: {plot_agg['plot_pol'].min():.2f}%, Max: {plot_agg['plot_pol'].max():.2f}%)")
print(f"   • Mean Plot CCS:               {plot_agg['plot_ccs'].mean():.2f}% (Min: {plot_agg['plot_ccs'].min():.2f}%, Max: {plot_agg['plot_ccs'].max():.2f}%)")
print(f"   • Mean Plot Early Recovery:    {plot_agg['plot_early_rec'].mean():.2f}% (Min: {plot_agg['plot_early_rec'].min():.2f}%, Max: {plot_agg['plot_early_rec'].max():.2f}%)")
print(f"   • Mean Plot Delivered Tonnage: {plot_agg['plot_tonnage'].mean():.2f} MT (Min: {plot_agg['plot_tonnage'].min():.2f} MT, Max: {plot_agg['plot_tonnage'].max():.2f} MT)")
print("-" * 70)

# Date breakdown
for dt, grp in df_crush.groupby('WSLIP_DATE'):
    ton = grp['NET_WT'].sum()
    w_pol = (grp['POL_JUICE'] * grp['NET_WT']).sum() / ton
    w_ccs = (grp['CCS'] * grp['NET_WT']).sum() / ton
    w_rec = (grp['EARLY_RECOVERY'] * grp['NET_WT']).sum() / ton
    print(f"Date {dt}: {len(grp):,} slips | {grp['DOCUMENT_NO'].nunique():,} plots | {ton:,.2f} MT | Pol: {w_pol:.2f}% | CCS: {w_ccs:.2f}% | Recovery: {w_rec:.2f}%")

print("-" * 70)
print("Top 10 Harvested Shivars / Circles by Tonnage & Recovery:")
shivar_summary = df_crush.groupby('SHIVAR_NAME').agg(
    tonnage=('NET_WT', 'sum'),
    plots=('DOCUMENT_NO', 'nunique'),
    w_pol=('POL_JUICE', lambda p: (p * df_crush.loc[p.index, 'NET_WT']).sum() / df_crush.loc[p.index, 'NET_WT'].sum()),
    w_ccs=('CCS', lambda c: (c * df_crush.loc[c.index, 'NET_WT']).sum() / df_crush.loc[c.index, 'NET_WT'].sum()),
    w_rec=('EARLY_RECOVERY', lambda r: (r * df_crush.loc[r.index, 'NET_WT']).sum() / df_crush.loc[r.index, 'NET_WT'].sum())
).sort_values(by='tonnage', ascending=False).head(10)

print(shivar_summary.to_string())
print("="*70)
