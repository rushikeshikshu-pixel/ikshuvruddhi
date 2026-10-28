import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# Load crushing data
excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
df_crush = pd.concat([xl.parse("25.10.2026"), xl.parse("26.10.2026")], ignore_index=True)
df_crush['DOCUMENT_NO'] = pd.to_numeric(df_crush['DOCUMENT_NO'], errors='coerce')
df_crush = df_crush.dropna(subset=['DOCUMENT_NO'])
df_crush['DOCUMENT_NO'] = df_crush['DOCUMENT_NO'].astype(int)

# Group by DOCUMENT_NO
crush_plot = df_crush.groupby('DOCUMENT_NO').agg(
    crushed_tonnage_mt=('NET_WT', 'sum'),
    crush_slips=('NET_WT', 'count'),
    crush_recovery_pct=('RECOVERY_PER', lambda r: (r * df_crush.loc[r.index, 'NET_WT']).sum() / df_crush.loc[r.index, 'NET_WT'].sum()),
    crush_dates=('WSLIP_DATE', lambda d: ', '.join(sorted(list(set(d.astype(str)))))),
    factory_grower_code=('GROWER_CODE', 'first'),
    factory_grower_name=('GROWER_NAME', 'first'),
    factory_shivar=('SHIVAR_NAME', 'first')
).reset_index()

print(f"Total Crushed Plots: {len(crush_plot)}")
print(f"Total Crushed Weight: {crush_plot['crushed_tonnage_mt'].sum():,.2f} MT")
print(f"Total Crushed Slips: {crush_plot['crush_slips'].sum():,}")
print(f"Weighted Average Factory Recovery: {(crush_plot['crushed_tonnage_mt'] * crush_plot['crush_recovery_pct']).sum() / crush_plot['crushed_tonnage_mt'].sum():.2f}%")

# Save aggregated crushing ground truth
crush_plot.to_csv('data/gangamai_crushing_25_26_oct2026_aggregated.csv', index=False, encoding='utf-8')
print("Saved aggregated crushing ground truth to data/gangamai_crushing_25_26_oct2026_aggregated.csv")
