import os
import sys
import pandas as pd
import numpy as np

"""
Automated CSV Data Cleaning & Preprocessing Pipeline
=====================================================
Cleans, standardizes, imputes, and sanitizes input CSV datasets before
running Satellite Telemetry API integration & Sucrose ML prediction.
"""

def clean_and_sanitize_csv(input_file="sugarcane_sucrose_dataset.csv", output_file="cleaned_sugarcane_dataset.csv"):
    print("==================================================================")
    print(" AUTOMATED CSV DATA CLEANING & PREPROCESSING PIPELINE")
    print(" Input Dataset :", input_file)
    print(" Output Dataset:", output_file)
    print("==================================================================")

    if not os.path.exists(input_file):
        print(f"[Error] File '{input_file}' does not exist!")
        return None, 0.0

    df = pd.read_csv(input_file)
    initial_rows = len(df)
    print(f"[1/5] Loaded raw dataset: {initial_rows} rows, {len(df.columns)} columns.")

    # 1. Standardize Column Names
    rename_dict = {}
    for col in df.columns:
        clean = col.strip().lower().replace(' ', '_').replace('-', '_')
        if clean in ['lat_1', 'lat1', 'latitude', 'lat_dd', 'lat']:
            rename_dict[col] = 'latitude'
        elif clean in ['long_1', 'long1', 'lon_1', 'lon1', 'longitude', 'long', 'lon', 'lng', 'lon_dd']:
            rename_dict[col] = 'longitude'
        elif clean in ['plantation_date', 'plant_date', 'plantationdate', 'plantdate', 'date']:
            rename_dict[col] = 'plantation_date'
        elif clean in ['plot_no', 'plotno', 'plot_number', 'field_id', 'farm_id']:
            rename_dict[col] = 'farm_id'
        elif clean in ['farmer', 'farmer_name', 'field_name']:
            rename_dict[col] = 'field_name'
        elif clean in ['variety_name', 'variety', 'cane_variety']:
            rename_dict[col] = 'cane_variety'
        elif clean in ['cane_type', 'planting_type', 'crop_type']:
            rename_dict[col] = 'planting_type'
        elif clean in ['age', 'crop_age', 'crop_age_days', 'days_to_harvest']:
            rename_dict[col] = 'crop_age_days'
        elif clean in ['ndvi', 'sat_ndvi', 'vegetation_index']:
            rename_dict[col] = 'sat_ndvi'
        elif clean in ['temp', 'temperature', 'sat_temp', 'sat_temp_celsius']:
            rename_dict[col] = 'sat_temp_celsius'

    df = df.rename(columns=rename_dict)
    print(f"[2/5] Standardized column headers: {list(df.columns)}")

    # Ensure Latitude and Longitude exist
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        print("[Error] Latitude and Longitude columns could not be identified!")
        return df, 0.0

    # 2. Convert numeric types & drop corrupt coordinates
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

    valid_coords_mask = (
        (df['latitude'].notnull()) & 
        (df['longitude'].notnull()) & 
        (df['latitude'] >= -90.0) & (df['latitude'] <= 90.0) &
        (df['longitude'] >= -180.0) & (df['longitude'] <= 180.0) &
        ~((df['latitude'] == 0.0) & (df['longitude'] == 0.0))
    )

    invalid_count = len(df) - valid_coords_mask.sum()
    if invalid_count > 0:
        print(f"[3/5] Removed {invalid_count} rows with invalid/corrupt coordinates.")
    df = df[valid_coords_mask].copy()

    # 3. Deduplicate Rows
    dupes = df.duplicated(subset=['latitude', 'longitude']).sum()
    if dupes > 0:
        print(f"  -> Dropped {dupes} duplicate location records.")
        df = df.drop_duplicates(subset=['latitude', 'longitude']).reset_index(drop=True)

    # 4. Process Plantation Date & Calculate Crop Age
    if 'crop_age_days' in df.columns:
        df['crop_age_days'] = pd.to_numeric(df['crop_age_days'], errors='coerce')

    if 'crop_age_days' not in df.columns or df['crop_age_days'].isnull().all():
        if 'plantation_date' in df.columns:
            print("  -> Calculating crop_age_days from 'plantation_date'...")
            parsed_dates = pd.to_datetime(df['plantation_date'].astype(str).str.replace(' ', '-').str.replace('/', '-'), dayfirst=True, errors='coerce')
            target_eval_date = pd.to_datetime('2025-11-25')
            computed_age = (target_eval_date - parsed_dates).dt.days
            df['crop_age_days'] = computed_age.fillna(360.0)
            print(f"  -> Successfully computed crop_age_days (Average: {df['crop_age_days'].mean():.1f} days).")
        else:
            df['crop_age_days'] = 360.0

    df['crop_age_days'] = df['crop_age_days'].fillna(360.0).clip(lower=120, upper=550)

    # 5. Impute Satellite Telemetry Fields
    if 'sat_ndvi' not in df.columns or df['sat_ndvi'].isnull().all():
        df['sat_ndvi'] = np.round(0.78 + np.sin(df['latitude'] * 10) * 0.05, 2)

    if 'sat_temp_celsius' not in df.columns: df['sat_temp_celsius'] = 32.5
    if 'sat_solar_radiation_kwh_m2' not in df.columns: df['sat_solar_radiation_kwh_m2'] = 7.8
    if 'sat_precipitation_mm' not in df.columns: df['sat_precipitation_mm'] = 0.0
    if 'sat_humidity_pct' not in df.columns: df['sat_humidity_pct'] = 45.0
    if 'sat_diurnal_temp_range' not in df.columns: df['sat_diurnal_temp_range'] = 12.5

    final_rows = len(df)
    retention_rate = (final_rows / initial_rows) * 100.0 if initial_rows > 0 else 100.0
    quality_score = round(min(100.0, max(50.0, retention_rate - (invalid_count * 2.0))), 1)

    df.to_csv(output_file, index=False)

    print("------------------------------------------------------------------")
    print(f"[4/5] Data Cleaning Completed!")
    print(f"  -> Initial Rows   : {initial_rows}")
    print(f"  -> Cleaned Rows   : {final_rows}")
    print(f"  -> Retention Rate : {retention_rate:.1f}%")
    print(f"  -> Data Quality Score: {quality_score}%")
    print(f"[5/5] Clean dataset written to '{output_file}'.")
    print("==================================================================\n")

    return df, quality_score

if __name__ == "__main__":
    infile = sys.argv[1] if len(sys.argv) > 1 else "sugarcane_sucrose_dataset.csv"
    outfile = sys.argv[2] if len(sys.argv) > 2 else "cleaned_sugarcane_dataset.csv"
    clean_and_sanitize_csv(infile, outfile)
