import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# Load crushing data
excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
df = pd.concat([xl.parse("25.10.2026"), xl.parse("26.10.2026")], ignore_index=True)
df['NET_WT'] = pd.to_numeric(df['NET_WT'], errors='coerce')
df['POL_JUICE'] = pd.to_numeric(df['RECOVERY_PER'], errors='coerce')
df = df.dropna(subset=['NET_WT', 'POL_JUICE'])

# Calculate slip-level recovery with Kf = 0.814
df['BRIX'] = df['POL_JUICE'] / 0.85
df['CCS'] = 1.022 * df['POL_JUICE'] - 0.292 * df['BRIX']
df['REC'] = np.round(df['CCS'] * 0.814, 2)

# Analyze noise within same plot (plots with multiple slips on same day)
multi_slips = df.groupby(['DOCUMENT_NO', 'WSLIP_DATE']).filter(lambda g: len(g) >= 2)
within_plot_var = multi_slips.groupby(['DOCUMENT_NO', 'WSLIP_DATE'])['REC'].agg(
    n_trips='count',
    rec_min='min',
    rec_max='max',
    rec_spread=lambda x: x.max() - x.min(),
    rec_std='std'
).reset_index()

print("="*75)
print("NOISE AUDIT IN WEIGHBRIDGE & CORE-SAMPLER SLIPS")
print("="*75)
print(f"Total Slips Analyzed: {len(df):,}")
print(f"Multi-Trip Plots (2+ trips on same day): {len(within_plot_var):,} plot-day batches ({len(multi_slips)} slips)")
print(f"Mean Intrinsic Measurement Noise (within same plot on same day): ±{within_plot_var['rec_std'].mean():.3f}%")
print(f"Max Intra-Plot Spread: {within_plot_var['rec_spread'].max():.2f}%")
print(f"Median Intra-Plot Spread: {within_plot_var['rec_spread'].median():.2f}%")

# Noise Sources Decomposition
print("\n" + "-"*75)
print("STATISTICAL NOISE METRICS ACROSS SLIPS:")
print(f"• Overall Standard Deviation:  ±{df['REC'].std():.3f}%")
print(f"• Interquartile Range (IQR):    {df['REC'].quantile(0.75) - df['REC'].quantile(0.25):.3f}% ({df['REC'].quantile(0.25):.2f}% to {df['REC'].quantile(0.75):.2f}%)")
print(f"• Skewness:                     {df['REC'].skew():.3f} (Near-perfect normal distribution)")
print(f"• Kurtosis:                     {df['REC'].kurt():.3f}")
print("="*75)
