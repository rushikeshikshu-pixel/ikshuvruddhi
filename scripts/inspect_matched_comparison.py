import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
df_crush = pd.concat([xl.parse("25.10.2026"), xl.parse("26.10.2026")], ignore_index=True)

# Clean DOCUMENT_NO
df_crush['DOCUMENT_NO'] = pd.to_numeric(df_crush['DOCUMENT_NO'], errors='coerce')
df_crush = df_crush.dropna(subset=['DOCUMENT_NO'])
df_crush['DOCUMENT_NO'] = df_crush['DOCUMENT_NO'].astype(int)

# Aggregate crushing by plot
crush_by_plot = df_crush.groupby('DOCUMENT_NO').agg(
    actual_crushed_mt=('NET_WT', 'sum'),
    slip_count=('NET_WT', 'count'),
    actual_mill_recovery=('RECOVERY_PER', lambda r: (r * df_crush.loc[r.index, 'NET_WT']).sum() / df_crush.loc[r.index, 'NET_WT'].sum()),
    crush_dates=('WSLIP_DATE', lambda d: ', '.join(sorted(list(set(d.astype(str)))))),
    grower_code=('GROWER_CODE', 'first'),
    grower_name=('GROWER_NAME', 'first'),
    shivar_name=('SHIVAR_NAME', 'first')
).reset_index()

df_master = pd.read_csv('data/output/all_unharvested_plots_oct2026_latest_satellite_register.csv', encoding='utf-8')
df_master['Plot No'] = pd.to_numeric(df_master['Plot No'], errors='coerce').astype(int)

merged = pd.merge(crush_by_plot, df_master, left_on='DOCUMENT_NO', right_on='Plot No', how='inner')
print(f"Matched {len(merged)} plots directly in unharvested register.")

# Look at actual crushed MT vs Standing / Harvested MT
merged['walked_ha'] = pd.to_numeric(merged['registered_area_ha'], errors='coerce').fillna(merged['Geodesic Walked Ha']).fillna(0.8)
merged['prior_yield'] = pd.to_numeric(merged['Yield (MT/Ha)'], errors='coerce').fillna(100.0)
merged['prior_standing_mt'] = pd.to_numeric(merged['Standing Millable Tonnage (MT)'], errors='coerce')
merged['prior_harvested_mt'] = pd.to_numeric(merged['Harvested Cut Tonnage (MT)'], errors='coerce')
merged['total_expected_mt'] = merged['walked_ha'] * merged['prior_yield']

merged['crushed_to_total_ratio'] = merged['actual_crushed_mt'] / merged['total_expected_mt']
merged['realized_yield_if_full'] = merged['actual_crushed_mt'] / merged['walked_ha']

print("\n--- Summary of Matched Crushed Plots ---")
print("Total Crushed Tonnage delivered from matched plots:", f"{merged['actual_crushed_mt'].sum():,.1f} MT")
print("Total Prior Standing Tonnage for these plots:", f"{merged['prior_standing_mt'].sum():,.1f} MT")
print("Total Expected Tonnage (Area * Yield):", f"{merged['total_expected_mt'].sum():,.1f} MT")
print(f"Crushed to Expected Ratio: Mean={merged['crushed_to_total_ratio'].mean():.2f}, Median={merged['crushed_to_total_ratio'].median():.2f}")
print(f"Actual Mill Lab Recovery: Mean={merged['actual_mill_recovery'].mean():.2f}%, Min={merged['actual_mill_recovery'].min():.2f}%, Max={merged['actual_mill_recovery'].max():.2f}%")

print("\nFirst 10 plots comparison:")
cols_show = ['DOCUMENT_NO', 'grower_name', 'shivar_name', 'walked_ha', 'prior_yield', 'actual_crushed_mt', 'prior_standing_mt', 'actual_mill_recovery']
print(merged[cols_show].head(10).to_string())
