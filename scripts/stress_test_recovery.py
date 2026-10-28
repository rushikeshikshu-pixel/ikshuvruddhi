import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# Load crushing slips
excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
df25 = xl.parse("25.10.2026")
df26 = xl.parse("26.10.2026")
df = pd.concat([df25, df26], ignore_index=True)
df['NET_WT'] = pd.to_numeric(df['NET_WT'], errors='coerce')
df['POL_JUICE'] = pd.to_numeric(df['RECOVERY_PER'], errors='coerce')
df = df.dropna(subset=['NET_WT', 'POL_JUICE'])

total_tonnage = df['NET_WT'].sum()
total_slips = len(df)
unique_plots = df['DOCUMENT_NO'].nunique()

print("="*75)
print(f"STRESS TEST & SENSITIVITY AUDIT: FACTORY RECOVERY REALIZATION")
print(f"Dataset: 1,694 Slips | 753 Plots | 15,277.50 MT Crushed Cane")
print("="*75)

# --- 1. SENSITIVITY MATRIX: Purity vs. Realization Factor ---
print("\n1. 2D SENSITIVITY MATRIX (Juice Purity vs Realization Factor Kf)")
print("Shows overall weighted recovery (%) under different chemical assumptions:")
print("-" * 75)

purities = [0.83, 0.84, 0.85, 0.86, 0.87]
factors = [0.800, 0.805, 0.810, 0.814, 0.820, 0.825]

header = f"{'Purity':<10}" + "".join([f"Kf={f:.3f}   " for f in factors])
print(header)
print("-" * 75)

for p in purities:
    row_str = f"{p*100:.1f}%      "
    for f in factors:
        brix = df['POL_JUICE'] / p
        ccs = 1.022 * df['POL_JUICE'] - 0.292 * brix
        rec = ccs * f
        w_rec = (rec * df['NET_WT']).sum() / total_tonnage
        row_str += f"{w_rec:.2f}%     "
    print(row_str)

# --- 2. STATISTICAL DISTRIBUTION OF THE BASELINE (Purity=85%, Kf=0.814) ---
df['BRIX_85'] = df['POL_JUICE'] / 0.85
df['CCS_85'] = 1.022 * df['POL_JUICE'] - 0.292 * df['BRIX_85']
df['REC_814'] = np.round(df['CCS_85'] * 0.814, 2)

w_rec_base = (df['REC_814'] * df['NET_WT']).sum() / total_tonnage
std_rec = np.sqrt(((df['REC_814'] - w_rec_base)**2 * df['NET_WT']).sum() / total_tonnage)
sem_rec = std_rec / np.sqrt(unique_plots)
ci_lower = w_rec_base - 1.96 * sem_rec
ci_upper = w_rec_base + 1.96 * sem_rec

print("\n" + "-" * 75)
print("2. STATISTICAL SPREAD & CONFIDENCE INTERVAL (at Kf = 0.814, Purity = 85%)")
print(f"   • Tonnage-Weighted Mean Recovery:  {w_rec_base:.2f}%")
print(f"   • Standard Deviation (Spread):     ±{std_rec:.2f}%")
print(f"   • Standard Error of Mean (SEM):    ±{sem_rec:.4f}%")
print(f"   • 95% Confidence Interval:         [{ci_lower:.2f}%, {ci_upper:.2f}%]")
print(f"   • Minimum Slip Recovery:           {df['REC_814'].min():.2f}% (Paudul Circle, immature ratoon)")
print(f"   • Maximum Slip Recovery:           {df['REC_814'].max():.2f}% (Dadegaon Jahangir, Adsali peak)")

# --- 3. RECOVERY BINS DISTRIBUTION (Where do plots fall?) ---
print("\n" + "-" * 75)
print("3. RECOVERY HISTOGRAM BINS (Plot Distribution across Recovery Tiers)")
bins = [0.0, 7.0, 7.25, 7.50, 7.75, 10.0]
labels = ['< 7.00% (Immature)', '7.00% - 7.24% (Low)', '7.25% - 7.49% (Core Avg)', '7.50% - 7.74% (Good)', '>= 7.75% (Superior)']
df['TIER'] = pd.cut(df['REC_814'], bins=bins, labels=labels)

tier_summary = df.groupby('TIER', observed=False).agg(
    tonnage=('NET_WT', 'sum'),
    slips=('NET_WT', 'count'),
    plots=('DOCUMENT_NO', 'nunique')
).reset_index()
tier_summary['tonnage_pct'] = (tier_summary['tonnage'] / total_tonnage) * 100

for _, r in tier_summary.iterrows():
    print(f"   • {r['TIER']:<24}: {r['tonnage']:>9,.1f} MT ({r['tonnage_pct']:>5.1f}%) | {r['plots']:>3} plots")

# --- 4. MONTE CARLO STRESS TEST: Perturbing Pol, Purity & Factory Losses ---
print("\n" + "-" * 75)
print("4. MONTE CARLO ROBUSTNESS STRESS TEST (10,000 Simulations)")
print("   Simulating random ±0.3% lab noise, transit delays (12h - 48h), and purity shifts:")

np.random.seed(42)
n_sim = 10000
sim_recoveries = []

# Base vectors
net_wt = df['NET_WT'].values
pol_raw = df['POL_JUICE'].values

for _ in range(n_sim):
    # Random lab polarimeter instrument error: normal(0, 0.15%)
    pol_noise = pol_raw + np.random.normal(0, 0.15, size=len(pol_raw))
    # Random purity variation across consignments: uniform(0.835, 0.865)
    purity_sim = np.random.uniform(0.835, 0.865, size=len(pol_raw))
    # Random factory boiling house efficiency fluctuation: uniform(0.808, 0.820)
    kf_sim = np.random.uniform(0.808, 0.820)
    
    brix_sim = pol_noise / purity_sim
    ccs_sim = 1.022 * pol_noise - 0.292 * brix_sim
    rec_sim = ccs_sim * kf_sim
    
    w_rec_sim = np.sum(rec_sim * net_wt) / total_tonnage
    sim_recoveries.append(w_rec_sim)

sim_recoveries = np.array(sim_recoveries)
print(f"   • Monte Carlo Mean Recovery:  {np.mean(sim_recoveries):.3f}%")
print(f"   • 5th Percentile (Worst-Case): {np.percentile(sim_recoveries, 5):.3f}%")
print(f"   • 50th Percentile (Median):   {np.percentile(sim_recoveries, 50):.3f}%")
print(f"   • 95th Percentile (Best-Case): {np.percentile(sim_recoveries, 95):.3f}%")
print(f"   • Max Theoretical Range:      {np.min(sim_recoveries):.2f}% to {np.max(sim_recoveries):.2f}%")
print("="*75)
