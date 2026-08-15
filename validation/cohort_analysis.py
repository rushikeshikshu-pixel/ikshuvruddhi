"""
validation/cohort_analysis.py
Cohort Analysis and Stratified Error Breakdown Reporter
"""

import os
import sys
import pandas as pd
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(REPO_ROOT, "data", "output", "refined_empirical_sentinel_analysis_88plots.csv")

def analyze_cohorts(csv_path=CSV_PATH):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return
        
    df = pd.read_csv(csv_path)
    print("==================================================================")
    print(" REPRODUCIBLE EMPIRICAL SENTINEL-2 CANOPY & OCCUPANCY AUDIT")
    print(f" Source CSV : {csv_path}")
    print(f" Total Plots: {len(df)}")
    print("==================================================================")
    
    print(f" Overall Dataset Metrics (N={len(df)}):")
    print(f"   -> Mean Field NDVI                         : {df['mean_field_ndvi'].mean():.3f}")
    print(f"   -> Mean Field NDRE                         : {df['mean_field_ndre'].mean():.3f}")
    print(f"   -> Mean Field LSWI                         : {df['mean_field_lswi'].mean():.3f}")
    print(f"   -> Mean Parcel Cane Occupancy              : {df['parcel_cane_occupancy_pct'].mean():.2f}%")
    print(f"   -> Mean Strict Parcel IoU                  : {df['strict_parcel_iou_pct'].mean():.2f}%")
    print(f"   -> Mean Estimated Boundary-Pixel Exposure  : {df['estimated_boundary_pixel_exposure_pct'].mean():.2f}%")
    print("------------------------------------------------------------------")
    
    high_ndvi = df[df['mean_field_ndvi'] >= 0.55]
    print(f" Conditional Cohort (NDVI >= 0.55, N={len(high_ndvi)}):")
    print(f"   -> Conditional Mean Parcel Cane Occupancy  : {high_ndvi['parcel_cane_occupancy_pct'].mean():.2f}%")
    print(f"   -> Conditional Mean Strict Parcel IoU      : {high_ndvi['strict_parcel_iou_pct'].mean():.2f}%")
    print(f"   -> Mean Estimated Boundary-Pixel Exposure  : {high_ndvi['estimated_boundary_pixel_exposure_pct'].mean():.2f}%")
    print("------------------------------------------------------------------")
    
    low_ndvi = df[df['mean_field_ndvi'] < 0.35]
    print(f" No Standing Vegetation Cohort (NDVI < 0.35, N={len(low_ndvi)}):")
    print(f"   -> Mean Field NDVI                         : {low_ndvi['mean_field_ndvi'].mean():.3f}")
    print(f"   -> Mean Parcel Cane Occupancy              : {low_ndvi['parcel_cane_occupancy_pct'].mean():.2f}%")
    print(f"   -> Mean Strict Parcel IoU                  : {low_ndvi['strict_parcel_iou_pct'].mean():.2f}%")
    print("------------------------------------------------------------------")
    
    print(" Stratified Error Attribution Breakdown:")
    for cat, count in df["primary_error_attribution"].value_counts().items():
        pct = (count / len(df)) * 100.0
        print(f"   [{count:2d} plots | {pct:4.1f}%] {cat}")
    print("==================================================================\n")

if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else CSV_PATH
    analyze_cohorts(csv_file)