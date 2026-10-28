import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
df_crush = pd.concat([xl.parse("25.10.2026"), xl.parse("26.10.2026")], ignore_index=True)
crush_docs = set(df_crush['DOCUMENT_NO'].unique())

df_unharv = pd.read_csv('data/output/all_unharvested_plots_oct2026_latest_satellite_register.csv', usecols=['Plot No'], encoding='utf-8')
unharv_plots = set(df_unharv['Plot No'].unique())

df_full = pd.read_csv('data/output/gangamai_command_area_full_master_29657plots_tonnage_diversion_register.csv', usecols=['Plot No'], encoding='utf-8')
full_plots = set(df_full['Plot No'].unique())

unmatched_unharv = crush_docs - unharv_plots
matched_in_full = unmatched_unharv.intersection(full_plots)

print(f"Total crushing plots: {len(crush_docs)}")
print(f"Matched in unharvested register (29,384 plots): {len(crush_docs.intersection(unharv_plots))}")
print(f"Unmatched in unharvested: {len(unmatched_unharv)}")
print(f"Of unmatched, found in 29,657 full master: {len(matched_in_full)}")
print(f"Still unmatched anywhere: {len(unmatched_unharv - matched_in_full)}")

# Look at details of the remaining
sample_rem = df_crush[df_crush['DOCUMENT_NO'].isin(unmatched_unharv - matched_in_full)][['DOCUMENT_NO', 'GROWER_CODE', 'GROWER_NAME', 'SHIVAR_NAME', 'NET_WT', 'RECOVERY_PER']].drop_duplicates('DOCUMENT_NO')
print("\nSample of plots not in either master register:")
print(sample_rem.head(10))
