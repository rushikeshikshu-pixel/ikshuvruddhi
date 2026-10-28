import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd

df = pd.read_csv('data/output/plots_32154_32308_pol_brix_ccs_quality_register.csv')
print(f"Total Plots: {len(df)}")
print(f"Pol Range: {df['predicted_pol_juice_pct'].min():.2f}% - {df['predicted_pol_juice_pct'].max():.2f}% (Mean: {df['predicted_pol_juice_pct'].mean():.2f}%)")
print(f"Brix Range: {df['predicted_brix_bx'].min():.2f}°Bx - {df['predicted_brix_bx'].max():.2f}°Bx (Mean: {df['predicted_brix_bx'].mean():.2f}°Bx)")
print(f"CCS Range: {df['predicted_ccs_pct'].min():.2f}% - {df['predicted_ccs_pct'].max():.2f}% (Mean: {df['predicted_ccs_pct'].mean():.2f}%)")
print(f"Recovery Range: {df['estimated_recovery_pct'].min():.2f}% - {df['estimated_recovery_pct'].max():.2f}% (Mean: {df['estimated_recovery_pct'].mean():.2f}%)")
print(f"Yield Range: {df['ml_predicted_yield_mt_ha'].min():.1f} - {df['ml_predicted_yield_mt_ha'].max():.1f} MT/Ha (Mean: {df['ml_predicted_yield_mt_ha'].mean():.1f} MT/Ha)")
print(f"Total Tonnage: {df['Standing Millable Tonnage (MT)'].sum():,.1f} MT")
print(f"Total Area: {df['Registered Ha'].sum():.2f} Ha")
print("\nTop 20 Plots:")
for i, r in df.head(20).iterrows():
    print(f"Plot {int(r['Plot No'])} | {r['Farmer Name'][:22]:<22} | {r['Village'][:14]:<14} | {r['Variety']:<8} | {r['Cane Type']:<14} | {r['Registered Ha']:4.1f}ha | Pol: {r['predicted_pol_juice_pct']:5.2f}% | Brix: {r['predicted_brix_bx']:5.2f}Bx | CCS: {r['predicted_ccs_pct']:5.2f}% | Rec: {r['estimated_recovery_pct']:4.2f}% | Yield: {r['ml_predicted_yield_mt_ha']:5.1f} MT/Ha | Ton: {r['Standing Millable Tonnage (MT)']:6.1f} MT | Score: {r['todni_priority_score']:4.1f}")
