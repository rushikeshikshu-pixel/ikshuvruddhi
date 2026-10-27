"""
Ingest Mill Test & Laboratory Polarimeter Results for Recently Harvested Plots.
Syncs measured readings to the live portal database and calculates accuracy metrics.
"""

import sys
import os
import json
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "outputs" / "recently_harvested_mill_test_template.csv"

def process_mill_test_results(input_file_path):
    print(f"Loading mill test results from: {input_file_path}")
    if str(input_file_path).endswith('.xlsx'):
        df = pd.read_excel(input_file_path)
    else:
        df = pd.read_csv(input_file_path)

    # Filter rows that have actual lab measurements entered
    valid = df.dropna(subset=['Lab_Measured_Brix_Bx', 'Lab_Measured_Pol_Pct']).copy()
    valid = valid[(valid['Lab_Measured_Brix_Bx'] > 0) & (valid['Lab_Measured_Pol_Pct'] > 0)]
    
    if len(valid) == 0:
        print("No measured rows found. Please fill in Lab_Measured_Brix_Bx and Lab_Measured_Pol_Pct.")
        return

    print(f"Found {len(valid)} completed mill test sample(s).")

    # Calculate lab chemistry
    valid['Lab_Calculated_Purity_Pct'] = (valid['Lab_Measured_Pol_Pct'] / valid['Lab_Measured_Brix_Bx']) * 100.0
    valid['Lab_Calculated_CCS_Pct'] = valid['Lab_Measured_Pol_Pct'] - 0.4 * (valid['Lab_Measured_Brix_Bx'] - valid['Lab_Measured_Pol_Pct'])
    valid['Mill_Actual_Recovery_Pct'] = valid['Lab_Calculated_CCS_Pct'] * 0.754

    # Calculate deviation vs satellite predictions
    valid['Brix_Error'] = valid['predicted_brix_bx'] - valid['Lab_Measured_Brix_Bx']
    valid['Pol_Error'] = valid['predicted_pol_juice_pct'] - valid['Lab_Measured_Pol_Pct']
    valid['CCS_Error'] = valid['predicted_ccs_pct'] - valid['Lab_Calculated_CCS_Pct']

    mae_ccs = np.abs(valid['CCS_Error']).mean()
    mae_pol = np.abs(valid['Pol_Error']).mean()
    mae_brix = np.abs(valid['Brix_Error']).mean()

    print("\n" + "="*50)
    print("SATELLITE VS. MILL LAB VALIDATION SUMMARY")
    print("="*50)
    print(f"Total Samples Tested: {len(valid)}")
    print(f"Mean Lab Measured Brix: {valid['Lab_Measured_Brix_Bx'].mean():.2f} °Bx")
    print(f"Mean Lab Measured Pol:  {valid['Lab_Measured_Pol_Pct'].mean():.2f} %")
    print(f"Mean Lab Measured CCS:  {valid['Lab_Calculated_CCS_Pct'].mean():.2f} %")
    print(f"Mean Lab Purity:        {valid['Lab_Calculated_Purity_Pct'].mean():.2f} %")
    print("-" * 50)
    print(f"CCS Mean Absolute Error (MAE):  ±{mae_ccs:.2f}% CCS")
    print(f"Pol Mean Absolute Error (MAE):  ±{mae_pol:.2f}% Pol")
    print(f"Brix Mean Absolute Error (MAE): ±{mae_brix:.2f}°Bx")
    print("="*50 + "\n")

    out_path = ROOT / "outputs" / "completed_mill_test_comparison.csv"
    valid.to_csv(out_path, index=False)
    print(f"Full cross-validation audit saved to: {out_path}")
    return valid

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--file', default=str(TEMPLATE_PATH))
    args = p.parse_args()
    process_mill_test_results(args.file)
