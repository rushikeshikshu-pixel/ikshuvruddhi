import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import json

df_master = pd.read_csv('data/output/all_unharvested_plots_oct2026_latest_satellite_register.csv', nrows=5, encoding='utf-8')
print("Master columns count:", len(df_master.columns))

# Check match
excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
df_crush = pd.concat([xl.parse("25.10.2026"), xl.parse("26.10.2026")], ignore_index=True)

df_all_plots = pd.read_csv('data/output/all_unharvested_plots_oct2026_latest_satellite_register.csv', usecols=['Plot No', 'Farmer Name', 'Village', 'Geodesic Walked Ha', 'Standing Millable Tonnage (MT)', 'Harvested Cut Tonnage (MT)'], encoding='utf-8')

crush_docs = set(df_crush['DOCUMENT_NO'].unique())
plot_nos = set(df_all_plots['Plot No'].unique())

overlap = crush_docs.intersection(plot_nos)
print(f"\nUnique Crushing Plots: {len(crush_docs)}")
print(f"Unique Master Plots: {len(plot_nos)}")
print(f"Exact Matches on Plot No: {len(overlap)} / {len(crush_docs)} ({len(overlap)/len(crush_docs)*100:.1f}%)")

# Aggregate crushing by DOCUMENT_NO
crush_agg = df_crush.groupby('DOCUMENT_NO').agg(
    total_crushed_mt=('NET_WT', 'sum'),
    slip_count=('NET_WT', 'count'),
    mean_recovery=('RECOVERY_PER', 'mean'),
    weighted_recovery=('RECOVERY_PER', lambda r: (r * df_crush.loc[r.index, 'NET_WT']).sum() / df_crush.loc[r.index, 'NET_WT'].sum()),
    grower_name=('GROWER_NAME', 'first'),
    shivar_name=('SHIVAR_NAME', 'first')
).reset_index()

print("\nSample aggregated crushing records:")
print(crush_agg.head(5))

# Check matched vs unmatched
matched = crush_agg[crush_agg['DOCUMENT_NO'].isin(plot_nos)]
unmatched = crush_agg[~crush_agg['DOCUMENT_NO'].isin(plot_nos)]
print(f"\nMatched aggregated: {len(matched)}, Unmatched aggregated: {len(unmatched)}")
if len(unmatched) > 0:
    print("Sample unmatched:\n", unmatched.head(5))

