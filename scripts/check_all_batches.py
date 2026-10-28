import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import glob

excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
df_crush = pd.concat([xl.parse("25.10.2026"), xl.parse("26.10.2026")], ignore_index=True)
crush_docs = set(df_crush['DOCUMENT_NO'].unique())

all_known_plots = set()
for f in [
    'data/output/all_unharvested_plots_oct2026_latest_satellite_register.csv',
    'data/output/gangamai_command_area_full_master_29657plots_tonnage_diversion_register.csv',
    'data/output/plots_31412_31579_latest_real_satellite_register.csv',
    'data/output/plots_31580_31726_latest_real_satellite_register.csv',
    'data/output/plots_31726_31862_latest_satellite_bhunaksha_register.csv',
    'data/output/plots_31863_31973_latest_satellite_bhunaksha_register.csv'
]:
    df_temp = pd.read_csv(f, usecols=['Plot No'], encoding='utf-8')
    all_known_plots.update(df_temp['Plot No'].unique())

print(f"Total unique known plots across all files: {len(all_known_plots)}")
print(f"Crushing plots matched: {len(crush_docs.intersection(all_known_plots))} / {len(crush_docs)}")
missing = crush_docs - all_known_plots
print(f"Missing from all registers: {len(missing)}")
if missing:
    print("Missing IDs:", sorted(list(missing)))
