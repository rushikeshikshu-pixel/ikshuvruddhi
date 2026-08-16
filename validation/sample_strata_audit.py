"""
validation/sample_strata_audit.py
Extracts two distinct inspection subsets with standard ground truth template columns:
  1. Operational Action Audit Sample (Extreme Cases for immediate mill field actions).
  2. Scientific Validation Sample (Stratified Random Sampling with seed for unbiased research evaluation).
"""

import os
import sys
import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(REPO_ROOT, "data", "output", "refined_empirical_sentinel_analysis_320plots.csv")
OPERATIONAL_CSV = os.path.join(REPO_ROOT, "data", "output", "field_audit_operational_extreme_45plots.csv")
SCIENTIFIC_CSV = os.path.join(REPO_ROOT, "data", "output", "field_audit_scientific_random_45plots.csv")

def add_ground_truth_inspection_columns(df):
    df = df.copy()
    df["actual_ground_crop"] = ""
    df["standing_cane_present_yes_no"] = ""
    df["harvested_yes_no"] = ""
    df["ground_estimated_standing_fraction_pct"] = ""
    df["crop_growth_stage"] = ""
    df["field_photo_ref"] = ""
    df["officer_inspection_date"] = ""
    df["officer_notes"] = ""
    return df

def generate_inspection_samples(n_per_stratum=15, random_seed=42):
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return

    df = pd.read_csv(CSV_PATH)
    valid_df = df[df["mean_field_ndvi"].notnull()].copy()
    disc_col = "registered_cane_canopy_discrepancy" if "registered_cane_canopy_discrepancy" in df.columns else "standing_cane_discrepancy_score"

    high_pool = valid_df[valid_df["mean_field_ndvi"] >= 0.55].copy()
    mid_pool  = valid_df[(valid_df["mean_field_ndvi"] >= 0.35) & (valid_df["mean_field_ndvi"] < 0.55)].copy()
    low_pool  = valid_df[valid_df["mean_field_ndvi"] < 0.35].copy()

    # 1. OPERATIONAL AUDIT SAMPLE (Extreme Cases)
    op_high = high_pool.sort_values("strict_parcel_iou_pct", ascending=False).head(n_per_stratum).copy()
    op_high["audit_stratum"] = "HIGH_CANOPY_CONGRUENCE (NDVI >= 0.55)"

    op_mid = mid_pool.sort_values("parcel_cane_occupancy_pct", ascending=True).head(n_per_stratum).copy()
    op_mid["audit_stratum"] = "INTERMEDIATE_DISCREPANCY (0.35 <= NDVI < 0.55)"

    op_low = low_pool.sort_values("mean_field_ndvi", ascending=True).head(n_per_stratum).copy()
    op_low["audit_stratum"] = "CRITICAL_DISCREPANCY_OR_FALLOW (NDVI < 0.35)"

    op_df = pd.concat([op_high, op_mid, op_low], ignore_index=True)
    op_df = add_ground_truth_inspection_columns(op_df)
    op_df.to_csv(OPERATIONAL_CSV, index=False)

    # 2. SCIENTIFIC VALIDATION SAMPLE (Stratified Random Sampling)
    sci_high = high_pool.sample(n=min(n_per_stratum, len(high_pool)), random_state=random_seed).copy()
    sci_high["audit_stratum"] = "HIGH_CANOPY_CONGRUENCE (NDVI >= 0.55)"

    sci_mid = mid_pool.sample(n=min(n_per_stratum, len(mid_pool)), random_state=random_seed).copy()
    sci_mid["audit_stratum"] = "INTERMEDIATE_DISCREPANCY (0.35 <= NDVI < 0.55)"

    sci_low = low_pool.sample(n=min(n_per_stratum, len(low_pool)), random_state=random_seed).copy()
    sci_low["audit_stratum"] = "CRITICAL_DISCREPANCY_OR_FALLOW (NDVI < 0.35)"

    sci_df = pd.concat([sci_high, sci_mid, sci_low], ignore_index=True)
    sci_df = add_ground_truth_inspection_columns(sci_df)
    sci_df.to_csv(SCIENTIFIC_CSV, index=False)

    print("==================================================================")
    print(" GENERATED DUAL FIELD VERIFICATION DATASETS")
    print("==================================================================")
    print(f" 1. Operational Extreme Sample (N={len(op_df)}) -> {OPERATIONAL_CSV}")
    print(f"    - High Congruence Mean Occ: {op_high['parcel_cane_occupancy_pct'].mean():.1f}%, Mean Discrepancy: {op_high[disc_col].mean():.2f}")
    print(f"    - Critical Discrepancy Mean Occ: {op_low['parcel_cane_occupancy_pct'].mean():.1f}%, Mean Discrepancy: {op_low[disc_col].mean():.2f}")
    print("------------------------------------------------------------------")
    print(f" 2. Scientific Stratified Random Sample (N={len(sci_df)}, seed={random_seed}) -> {SCIENTIFIC_CSV}")
    print(f"    - High Congruence Mean Occ: {sci_high['parcel_cane_occupancy_pct'].mean():.1f}%, Mean Discrepancy: {sci_high[disc_col].mean():.2f}")
    print(f"    - Intermediate Mean Occ: {sci_mid['parcel_cane_occupancy_pct'].mean():.1f}%, Mean Discrepancy: {sci_mid[disc_col].mean():.2f}")
    print(f"    - Critical Discrepancy Mean Occ: {sci_low['parcel_cane_occupancy_pct'].mean():.1f}%, Mean Discrepancy: {sci_low[disc_col].mean():.2f}")
    print("==================================================================\n")

if __name__ == "__main__":
    generate_inspection_samples()