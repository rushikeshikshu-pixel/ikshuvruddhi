"""
validation/sample_strata_audit.py
Extracts a balanced audit sample across High Canopy, Intermediate, and Low Canopy Strata
for mill agriculture officer field verification.
"""

import os
import sys
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(REPO_ROOT, "data", "output", "refined_empirical_sentinel_analysis_320plots.csv")
OUT_SAMPLE_CSV = os.path.join(REPO_ROOT, "data", "output", "field_verification_audit_sample_45plots.csv")

def extract_balanced_audit_sample(n_per_stratum=15):
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return

    df = pd.read_csv(CSV_PATH)
    
    high = df[df["mean_field_ndvi"] >= 0.55].sort_values("strict_parcel_iou_pct", ascending=False).head(n_per_stratum).copy()
    high["audit_cohort"] = "HIGH_CANOPY_CONGRUENCE (NDVI >= 0.55)"

    mid = df[(df["mean_field_ndvi"] >= 0.35) & (df["mean_field_ndvi"] < 0.55)].sort_values("parcel_cane_occupancy_pct", ascending=True).head(n_per_stratum).copy()
    mid["audit_cohort"] = "INTERMEDIATE_DISCREPANCY (0.35 <= NDVI < 0.55)"

    low = df[df["mean_field_ndvi"] < 0.35].sort_values("mean_field_ndvi", ascending=True).head(n_per_stratum).copy()
    low["audit_cohort"] = "CRITICAL_DISCREPANCY_OR_FALLOW (NDVI < 0.35)"

    sample_df = pd.concat([high, mid, low], ignore_index=True)
    sample_df.to_csv(OUT_SAMPLE_CSV, index=False)
    
    print("==================================================================")
    print(f" EXTRACTED BALANCED FIELD VERIFICATION AUDIT SAMPLE (N={len(sample_df)})")
    print(f" Output File: {OUT_SAMPLE_CSV}")
    print("==================================================================")
    print(f" 1. High Canopy Congruence : {len(high)} plots (Mean Occ: {high['parcel_cane_occupancy_pct'].mean():.1f}%, Mean Discrepancy: {high['standing_cane_discrepancy_score'].mean():.2f})")
    print(f" 2. Intermediate / Mixed   : {len(mid)} plots (Mean Occ: {mid['parcel_cane_occupancy_pct'].mean():.1f}%, Mean Discrepancy: {mid['standing_cane_discrepancy_score'].mean():.2f})")
    print(f" 3. Critical Discrepancy   : {len(low)} plots (Mean Occ: {low['parcel_cane_occupancy_pct'].mean():.1f}%, Mean Discrepancy: {low['standing_cane_discrepancy_score'].mean():.2f})")
    print("==================================================================\n")
    return sample_df

if __name__ == "__main__":
    extract_balanced_audit_sample()