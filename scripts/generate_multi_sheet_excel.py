# -*- coding: utf-8 -*-
import os
import sys
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DL_DIR = os.path.expanduser('~\\Downloads')

# Sheet 1: Daily Crush Progression
progression_data = [
    {
        'Crush Date': '01 November 2026',
        'Plots Crushed': 249,
        'Crushed Cane (MT)': 5000.0,
        'Factory Daily Recovery (%)': 8.21,
        'Cumulative Season Average (%)': 7.71,
        'Cumulative Sugar Produced (MT)': 4105.0,
        'Daily Sugar Gain (MT / 5,000 MT crush)': 25.0,
        'Operational Ripening Driver': 'Opening November stream; Adsali plots entering carrier; ambient minimum temperature ~17.5°C.'
    },
    {
        'Crush Date': '02 November 2026',
        'Plots Crushed': 244,
        'Crushed Cane (MT)': 5000.0,
        'Factory Daily Recovery (%)': 8.31,
        'Cumulative Season Average (%)': 7.74,
        'Cumulative Sugar Produced (MT)': 4515.5,
        'Daily Sugar Gain (MT / 5,000 MT crush)': 28.5,
        'Operational Ripening Driver': 'Winter transition; night temperatures drop to 16.0°C; initial cold-induced sucrose translocation surge (+0.10%).'
    },
    {
        'Crush Date': '03 November 2026',
        'Plots Crushed': 173,
        'Crushed Cane (MT)': 3500.0,
        'Factory Daily Recovery (%)': 8.44,
        'Cumulative Season Average (%)': 7.75,
        'Cumulative Sugar Produced (MT)': 4796.4,
        'Daily Sugar Gain (MT / 5,000 MT crush)': 34.5,
        'Operational Ripening Driver': 'Peak cold night chilling (Tmin 14.5°C); high-purity (90%+) Adsali entering carrier with streamlined <18h transit (+0.13%).'
    }
]
df_prog = pd.DataFrame(progression_data)

# Sheet 2: Harvested Plots Audit Cross-Check
audit_data = [
    {
        'Crush Period': 'Opening Startup Crush (Oct 22 - Oct 31)',
        'Plots Harvested': 2393,
        'Area (Ha)': 2393.0,
        'Area (Acres)': 4145.3,
        'Crushed Cane (MT)': 48477.7,
        'Share of Crush (%)': 78.2,
        'Average Yield (MT/Plot)': 20.3,
        'Mean Realized Recovery (%)': 7.58,
        'Field Potential Recovery (%)': 7.65,
        'Sugar Produced (MT)': 3674.6
    },
    {
        'Crush Period': '01 November 2026 Stream',
        'Plots Harvested': 249,
        'Area (Ha)': 249.0,
        'Area (Acres)': 431.3,
        'Crushed Cane (MT)': 5000.0,
        'Share of Crush (%)': 8.1,
        'Average Yield (MT/Plot)': 20.1,
        'Mean Realized Recovery (%)': 8.21,
        'Field Potential Recovery (%)': 8.05,
        'Sugar Produced (MT)': 410.5
    },
    {
        'Crush Period': '02 November 2026 Stream',
        'Plots Harvested': 244,
        'Area (Ha)': 244.0,
        'Area (Acres)': 422.7,
        'Crushed Cane (MT)': 5000.0,
        'Share of Crush (%)': 8.1,
        'Average Yield (MT/Plot)': 20.5,
        'Mean Realized Recovery (%)': 8.31,
        'Field Potential Recovery (%)': 8.16,
        'Sugar Produced (MT)': 415.5
    },
    {
        'Crush Period': '03 November 2026 Stream',
        'Plots Harvested': 173,
        'Area (Ha)': 173.0,
        'Area (Acres)': 299.7,
        'Crushed Cane (MT)': 3500.0,
        'Share of Crush (%)': 5.6,
        'Average Yield (MT/Plot)': 20.2,
        'Mean Realized Recovery (%)': 8.44,
        'Field Potential Recovery (%)': 8.35,
        'Sugar Produced (MT)': 295.4
    },
    {
        'Crush Period': 'TOTAL CUMULATIVE SEASON TO DATE',
        'Plots Harvested': 3059,
        'Area (Ha)': 3059.0,
        'Area (Acres)': 5299.5,
        'Crushed Cane (MT)': 61977.7,
        'Share of Crush (%)': 100.0,
        'Average Yield (MT/Plot)': 20.3,
        'Mean Realized Recovery (%)': 7.74,
        'Field Potential Recovery (%)': 7.76,
        'Sugar Produced (MT)': 4796.4
    }
]
df_audit = pd.DataFrame(audit_data)

out_xlsx = os.path.join(ROOT, 'data', 'output', 'Gangamai_Daily_Crush_Progression_Nov2026.xlsx')
dl_xlsx = os.path.join(DL_DIR, 'Gangamai_Daily_Crush_Progression_Nov2026.xlsx')

with pd.ExcelWriter(out_xlsx, engine='openpyxl') as writer:
    df_prog.to_excel(writer, sheet_name='Daily_Progression', index=False)
    df_audit.to_excel(writer, sheet_name='Harvested_Audit_Crosscheck', index=False)

import shutil
shutil.copy(out_xlsx, dl_xlsx)
print(f"Generated multi-sheet Excel workbook at {out_xlsx} and {dl_xlsx}!")
