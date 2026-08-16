"""
validation/cohort_analysis.py
Cohort Analysis and Mill Operational Discrepancy Reporter
"""

import os
import sys
import pandas as pd
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(REPO_ROOT, "data", "output", "refined_empirical_sentinel_analysis_320plots.csv")

def analyze_cohorts(csv_path=CSV_PATH):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return
        
    df = pd.read_csv(csv_path)
    stratum_col = "diagnostic_stratum" if "diagnostic_stratum" in df.columns else "primary_error_attribution"
    
    print("==================================================================")
    print(" REPRODUCIBLE EMPIRICAL SENTINEL-2 CANOPY & DISCREPANCY AUDIT")
    print(f" Source CSV : {csv_path}")
    print(f" Total Plots: {len(df)}")
    print("==================================================================")
    
    print(f" Overall Dataset Metrics (N={len(df)}):")
    print(f"   -> Mean Usable Observation Coverage        : {df['parcel_valid_observation_pct'].mean():.2f}%")
    print(f"   -> Mean Parcel-Masked NDVI                 : {df['mean_field_ndvi'].mean():.3f}")
    print(f"   -> Mean Parcel-Masked NDRE                 : {df['mean_field_ndre'].mean():.3f}")
    print(f"   -> Mean Parcel-Masked LSWI                 : {df['mean_field_lswi'].mean():.3f}")
    print(f"   -> Mean Parcel Canopy Occupancy            : {df['parcel_cane_occupancy_pct'].mean():.2f}%")
    print(f"   -> Mean Strict Parcel IoU                  : {df['strict_parcel_iou_pct'].mean():.2f}%")
    print(f"   -> Mean Standing Cane Discrepancy Score    : {df['standing_cane_discrepancy_score'].mean():.3f}")
    print("------------------------------------------------------------------")
    
    high_ndvi = df[df['mean_field_ndvi'] >= 0.55]
    print(f" Registered Cane + Strong Standing Canopy (NDVI >= 0.55, N={len(high_ndvi)}):")
    print(f"   -> Mean Parcel-Masked NDVI                 : {high_ndvi['mean_field_ndvi'].mean():.3f}")
    print(f"   -> Mean Parcel Canopy Occupancy            : {high_ndvi['parcel_cane_occupancy_pct'].mean():.2f}%")
    print(f"   -> Mean Strict Parcel IoU                  : {high_ndvi['strict_parcel_iou_pct'].mean():.2f}%")
    print(f"   -> Mean Standing Cane Discrepancy Score    : {high_ndvi['standing_cane_discrepancy_score'].mean():.3f}")
    print("------------------------------------------------------------------")

    mid_ndvi = df[(df['mean_field_ndvi'] >= 0.35) & (df['mean_field_ndvi'] < 0.55)]
    print(f" Partial / Stressed / Mixed Canopy Stratum (0.35 <= NDVI < 0.55, N={len(mid_ndvi)}):")
    print(f"   -> Mean Parcel-Masked NDVI                 : {mid_ndvi['mean_field_ndvi'].mean():.3f}")
    print(f"   -> Mean Parcel Canopy Occupancy            : {mid_ndvi['parcel_cane_occupancy_pct'].mean():.2f}%")
    print(f"   -> Mean Strict Parcel IoU                  : {mid_ndvi['strict_parcel_iou_pct'].mean():.2f}%")
    print(f"   -> Mean Standing Cane Discrepancy Score    : {mid_ndvi['standing_cane_discrepancy_score'].mean():.3f}")
    print("------------------------------------------------------------------")
    
    low_ndvi = df[df['mean_field_ndvi'] < 0.35]
    print(f" No Strong Standing Canopy / Fallow Stratum (NDVI < 0.35, N={len(low_ndvi)}):")
    print(f"   -> Mean Parcel-Masked NDVI                 : {low_ndvi['mean_field_ndvi'].mean():.3f}")
    print(f"   -> Mean Parcel Canopy Occupancy            : {low_ndvi['parcel_cane_occupancy_pct'].mean():.2f}%")
    print(f"   -> Mean Strict Parcel IoU                  : {low_ndvi['strict_parcel_iou_pct'].mean():.2f}%")
    print(f"   -> Mean Standing Cane Discrepancy Score    : {low_ndvi['standing_cane_discrepancy_score'].mean():.3f}")
    print("------------------------------------------------------------------")
    
    print(" Diagnostic Stratum Breakdown:")
    for cat, count in df[stratum_col].value_counts().items():
        pct = (count / len(df)) * 100.0
        print(f"   [{count:3d} plots | {pct:4.1f}%] {cat}")
    print("==================================================================\n")

if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else CSV_PATH
    analyze_cohorts(csv_file)