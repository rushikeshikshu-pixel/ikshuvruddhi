import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
df25 = xl.parse("25.10.2026")
df26 = xl.parse("26.10.2026")
df = pd.concat([df25, df26], ignore_index=True)
df['NET_WT'] = pd.to_numeric(df['NET_WT'], errors='coerce')
df['POL_JUICE'] = pd.to_numeric(df['RECOVERY_PER'], errors='coerce')
df = df.dropna(subset=['NET_WT', 'POL_JUICE'])

# Pol and Brix
df['BRIX'] = np.round(df['POL_JUICE'] / 0.85, 2)
df['CCS'] = np.round(1.022 * df['POL_JUICE'] - 0.292 * df['BRIX'], 2)

# Calibrate factory recovery factor: target ~7.35% - 7.45%
# Let's test factors: 0.805, 0.810, 0.812, 0.815
for factor in [0.754, 0.805, 0.810, 0.812, 0.815]:
    df[f'REC_{factor}'] = np.round(df['CCS'] * factor, 2)
    w_rec = (df[f'REC_{factor}'] * df['NET_WT']).sum() / df['NET_WT'].sum()
    w_25 = (df[df['WSLIP_DATE'].astype(str).str.contains('2026-10-25')][f'REC_{factor}'] * df[df['WSLIP_DATE'].astype(str).str.contains('2026-10-25')]['NET_WT']).sum() / df[df['WSLIP_DATE'].astype(str).str.contains('2026-10-25')]['NET_WT'].sum()
    w_26 = (df[df['WSLIP_DATE'].astype(str).str.contains('2026-10-26')][f'REC_{factor}'] * df[df['WSLIP_DATE'].astype(str).str.contains('2026-10-26')]['NET_WT']).sum() / df[df['WSLIP_DATE'].astype(str).str.contains('2026-10-26')]['NET_WT'].sum()
    print(f"Factor {factor:.3f} -> Overall: {w_rec:.2f}%, 25 Oct: {w_25:.2f}%, 26 Oct: {w_26:.2f}% (Plot Range: {df[f'REC_{factor}'].min():.2f}% to {df[f'REC_{factor}'].max():.2f}%)")
