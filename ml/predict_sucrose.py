import sys
import os
import pandas as pd
import numpy as np
from sota_heteroscedastic_engine import HeteroscedasticConformalEngine

def run_heteroscedastic_pipeline(input_csv, output_csv):
    print("==================================================================")
    print(" 2026 SOTA HETEROSCEDASTIC QUANTILE CONFORMAL SUCROSE ENGINE")
    print(f" Input File : {input_csv}")
    print(f" Output File: {output_csv}")
    print("==================================================================")

    if not os.path.exists(input_csv):
        print(f"Error: Input CSV '{input_csv}' not found.")
        sys.exit(1)

    df = pd.read_csv(input_csv)
    print(f"[1/3] Loaded dataset: {len(df)} rows, {len(df.columns)} columns.")

    engine = HeteroscedasticConformalEngine()
    enriched = engine.predict_heteroscedastic(df, confidence=0.95)

    print("------------------------------------------------------------------")
    print(" 2026 HETEROSCEDASTIC MODEL ACCURACY & SPATIAL VALIDATION")
    print("------------------------------------------------------------------")
    print(f"  Field-Blocked Group CV R² Accuracy : {engine.r2_score * 100:.2f}%")
    print("  Uncertainty Framework               : Heteroscedastic Field-Specific Quantiles")
    print("------------------------------------------------------------------\n")

    print(" FIELD SUCROSE PREDICTIONS & HETEROSCEDASTIC UNCERTAINTY SUMMARY")
    print("------------------------------------------------------------------")
    for i in range(len(enriched)):
        row = enriched.iloc[i]
        farm_id = row.get('farm_id', f'Plot #{i+1}')
        farmer = row.get('farmer_name', row.get('Farmer', 'Farmer Member'))
        plant_type = row.get('planting_type', 'Suru')
        
        pol = row['pred_juice_pol']
        pol_l90 = row['pol_lower_90']
        pol_u90 = row['pol_upper_90']
        pol_l95 = row['pol_lower_95']
        pol_u95 = row['pol_upper_95']

        ccs = row['pred_ccs']
        ccs_l90 = row['ccs_lower_90']
        ccs_u90 = row['ccs_upper_90']

        cwsi = row.get('cwsi', 0.35)
        gndvi = row.get('sat_gndvi', 0.71)
        uncertainty_type = row.get('heteroscedastic_uncertainty_type', 'Standard')

        print(f" Plot [{farm_id}] {farmer} | {plant_type}")
        print(f"   -> Telemetry: GNDVI: {gndvi:.2f} | CWSI Water Stress: {cwsi:.2f} [{uncertainty_type}]")
        print(f"   -> Juice Pol (50% Median): {pol}% | 90% Bound: [{pol_l90}%, {pol_u90}%] | 95% Bound: [{pol_l95}%, {pol_u95}%]")
        print(f"   -> CCS Sugar             : {ccs}% | 90% Bound: [{ccs_l90}%, {ccs_u90}%]")
        print("------------------------------------------------------------------")

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    enriched.to_csv(output_csv, index=False)
    print(f"\n==================================================================")
    print(f" Heteroscedastic Predictions Successfully Saved To: {output_csv}")
    print("==================================================================")

if __name__ == "__main__":
    in_file = sys.argv[1] if len(sys.argv) > 1 else "data/sample/farmer_sample_input.csv"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "data/output/farmer_heteroscedastic_predictions.csv"
    run_heteroscedastic_pipeline(in_file, out_file)
