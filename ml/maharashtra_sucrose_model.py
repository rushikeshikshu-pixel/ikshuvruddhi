import os
import sys
import csv
import math
import pandas as pd
import numpy as np

"""
Ahilyanagar & Maharashtra Sugarcane Factory Recovery & CCS Engine
===================================================================
Calibrated for Maharashtra Sugar Factories (Karkhanas):
  - Factory Sugar Recovery % (Actual sugar bagged at mill: 10.2% to 12.8%)
  - Commercial Cane Sugar % (CCS %: 11.0% to 13.8%)
  - Laboratory Juice Sucrose Pol % (13.2% to 16.2%)
"""

VARIETY_COEFFS = {
    'CO 11015': 1.04,   # Early high sugar variety
    'CO 94012': 1.03,   # High sucrose
    'CO 86032': 1.01,   # Benchmark Maharashtra variety (Nira)
    'MS 10001': 1.00,   # Phule 10001
    'COM 0265': 0.96,   # High tonnage, moderate sucrose
    'DEFAULT': 1.00
}

PLANTING_MATURITY_CURVES = {
    'ADSALI': {'optimal_days': 430, 'base_recovery': 12.2},
    'PRE-SEASONAL': {'optimal_days': 380, 'base_recovery': 11.8},
    'SURU': {'optimal_days': 345, 'base_recovery': 11.2},
    'RATOON': {'optimal_days': 310, 'base_recovery': 10.8},
    'DEFAULT': {'optimal_days': 350, 'base_recovery': 11.2}
}

def predict_maharashtra_sucrose(input_csv="ahilyanagar_maharashtra_sugarcane.csv", output_csv="ahilyanagar_sucrose_predictions.csv"):
    print("==================================================================")
    print(" AHILYANAGAR & MAHARASHTRA SUGAR FACTORY RECOVERY & CCS ENGINE")
    print(" Input Dataset :", input_csv)
    print(" Output Dataset:", output_csv)
    print("==================================================================")

    if not os.path.exists(input_csv):
        print(f"[Error] File '{input_csv}' not found!")
        return

    df = pd.read_csv(input_csv)
    print(f"[Info] Loaded {len(df)} field observations across Ahilyanagar & Maharashtra.\n")

    factory_recovery_list = []
    ccs_list = []
    juice_sucrose_list = []
    harvest_recommendations = []

    for idx, row in df.iterrows():
        variety = str(row.get('cane_variety', 'DEFAULT')).strip().upper()
        planting = str(row.get('planting_type', 'DEFAULT')).strip().upper()
        age = float(row.get('crop_age_days', 350))
        ndvi = float(row.get('sat_ndvi', 0.78))
        temp = float(row.get('sat_temp_celsius', 33.0))
        solar = float(row.get('sat_solar_radiation_kwh_m2', 7.8))
        precip = float(row.get('sat_precipitation_mm', 0.0))
        dtr = float(row.get('sat_diurnal_temp_range', 12.5))

        var_coeff = VARIETY_COEFFS.get(variety, VARIETY_COEFFS['DEFAULT'])
        plant_info = PLANTING_MATURITY_CURVES.get(planting, PLANTING_MATURITY_CURVES['DEFAULT'])

        # Maturity Curve: Peak recovery around optimal harvest days
        optimal_age = plant_info['optimal_days']
        age_ratio = min(1.10, max(0.70, age / optimal_age))
        maturity_factor = math.sin(min(math.pi / 2.0, age_ratio * (math.pi / 2.0)))

        ndvi_factor = 0.90 + (ndvi * 0.15)
        solar_factor = 0.92 + (min(solar, 9.0) / 8.0) * 0.12
        dtr_factor = 0.94 + (min(dtr, 15.0) / 12.0) * 0.10
        water_factor = 1.03 if precip < 0.2 else (0.93 if precip > 4.0 else 1.0)

        # 1. Factory Sugar Recovery % (Real Sugar Bagged at Karkhana: 10.2% to 12.8%)
        base_rec = plant_info['base_recovery'] * maturity_factor * ndvi_factor * solar_factor * dtr_factor * water_factor * var_coeff
        mill_recovery_pct = round(min(12.85, max(9.80, base_rec)), 2)

        # 2. Commercial Cane Sugar % (CCS %: ~ Recovery / 0.92)
        ccs_pct = round(min(13.90, max(10.50, mill_recovery_pct / 0.92)), 2)

        # 3. Laboratory Juice Sucrose Pol % (Juice Pol: ~ CCS * 1.18)
        juice_sucrose_pct = round(min(16.50, max(12.20, ccs_pct * 1.18)), 2)

        factory_recovery_list.append(mill_recovery_pct)
        ccs_list.append(ccs_pct)
        juice_sucrose_list.append(juice_sucrose_pct)

        if mill_recovery_pct >= 12.0:
            rec = "PEAK HARVEST: High Factory Recovery (>12.0%). Crushing Token Recommended!"
        elif mill_recovery_pct >= 11.0:
            rec = "OPTIMAL HARVEST: Good Recovery (11.0%-12.0%). Schedule Mill Delivery."
        elif mill_recovery_pct >= 10.2:
            rec = "MODERATE: Average Recovery (10.2%-11.0%). Allow 2-3 Weeks Further Ripening."
        else:
            rec = "IMMATURE / LOW: Recovery (<10.2%). Hold Harvest & Withhold Water."

        harvest_recommendations.append(rec)

    df['factory_sugar_recovery_pct'] = factory_recovery_list
    df['ccs_sugar_pct'] = ccs_list
    df['juice_sucrose_pol_pct'] = juice_sucrose_list
    df['harvest_recommendation'] = harvest_recommendations

    df.to_csv(output_csv, index=False)

    print("------------------------------------------------------------------")
    print(" AHILYANAGAR & MAHARASHTRA FACTORY RECOVERY PREDICTIONS")
    print("------------------------------------------------------------------")
    for idx, row in df.iterrows():
        print(f" [{row.get('farm_id')}] {row.get('field_name')} ({row.get('tehsil_district')})")
        print(f"   -> Variety: {row.get('cane_variety')} | Type: {row.get('planting_type')} ({row.get('crop_age_days')} days)")
        print(f"   -> Factory Sugar Recovery: {row['factory_sugar_recovery_pct']}% | CCS Sugar: {row['ccs_sugar_pct']}% | Juice Pol: {row['juice_sucrose_pol_pct']}%")
        print(f"   -> Action: {row['harvest_recommendation']}")
        print("------------------------------------------------------------------")

    print("\n==================================================================")
    print(" AHILYANAGAR & MAHARASHTRA STATISTICAL SUMMARY")
    print("==================================================================")
    print(f"  Mean Factory Sugar Recovery % : {np.mean(factory_recovery_list):.2f} % (Mill Bagged Sugar)")
    print(f"  Mean CCS Sugar %             : {np.mean(ccs_list):.2f} %")
    print(f"  Mean Juice Sucrose Pol %     : {np.mean(juice_sucrose_list):.2f} %")
    print(f"  Highest Recovery Field       : {np.max(factory_recovery_list):.2f} % ({df.loc[np.argmax(factory_recovery_list), 'field_name']})")
    print(f"  Output CSV Saved             : {output_csv}")
    print("==================================================================")

if __name__ == "__main__":
    infile = sys.argv[1] if len(sys.argv) > 1 else "ahilyanagar_maharashtra_sugarcane.csv"
    outfile = sys.argv[2] if len(sys.argv) > 2 else "ahilyanagar_sucrose_predictions.csv"
    predict_maharashtra_sucrose(infile, outfile)
