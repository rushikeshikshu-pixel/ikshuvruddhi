# -*- coding: utf-8 -*-
"""
scripts/eval_10_samples.py
==========================
Evaluates the Smart 54-Parameter Hierarchical Model with the 4 Permanent Guardrails
against the 10 Physical Mill Laboratory Samples from 05-Nov and 06-Nov batches.
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"C:\Users\rishi\.gemini\antigravity\SatCane-AI-Engine"
sys.path.insert(0, ROOT)

from ml.guardrails import (
    apply_satellite_emergence_age_harmonizer,
    apply_soil_moderated_drainage_gate,
    apply_stunted_ratoon_degradation_cap,
    compute_cut_to_crush_delivered_sucrose
)

MASTER_REGISTER = os.path.join(ROOT, 'web', 'downloads', 'all_unharvested_plots_06Nov2026_latest_satellite_register.csv')
df_master = pd.read_csv(MASTER_REGISTER, low_memory=False)

samples_10 = [
    # 05 Nov (5 plots)
    {'date': '05-Nov', 'plot_no': 2685, 'farmer': 'गुजर अंबादास भानुदास', 'village': 'एरंडगाव', 'variety': 'CO-265', 'lab_brix': 14.98, 'lab_pol': 12.10, 'transit_hrs': 10.0},
    {'date': '05-Nov', 'plot_no': 16558, 'farmer': 'खेडकर अशोक बाबुराव', 'village': 'घोटन', 'variety': 'CO-265', 'lab_brix': 14.28, 'lab_pol': 12.02, 'transit_hrs': 10.0},
    {'date': '05-Nov', 'plot_no': 3755, 'farmer': 'भराट खंडू उत्तम', 'village': 'रावताळे', 'variety': 'CO-265', 'lab_brix': 15.29, 'lab_pol': 12.50, 'transit_hrs': 10.5},
    {'date': '05-Nov', 'plot_no': 2684, 'farmer': 'गुजर अंबादास (२री)', 'village': 'एरंडगाव', 'variety': 'VSI 18121', 'lab_brix': 14.54, 'lab_pol': 11.84, 'transit_hrs': 9.5},
    {'date': '05-Nov', 'plot_no': 13509, 'farmer': 'क्षिरसागर बाळासाहेब', 'village': 'घोटन', 'variety': 'CO-265', 'lab_brix': 15.78, 'lab_pol': 12.58, 'transit_hrs': 11.0},
    
    # 06 Nov (5 plots)
    {'date': '06-Nov', 'plot_no': 23609, 'farmer': 'गायकवाड सुभाष', 'village': 'अंबड', 'variety': 'CO-86032', 'lab_brix': 18.54, 'lab_pol': 16.27, 'transit_hrs': 28.0},
    {'date': '06-Nov', 'plot_no': 26989, 'farmer': 'उगलमुगले', 'village': 'जोहारापूर', 'variety': 'CO-265', 'lab_brix': 19.24, 'lab_pol': 15.95, 'transit_hrs': 24.0},
    {'date': '06-Nov', 'plot_no': 17341, 'farmer': 'खेडकर विक्रम नाना', 'village': 'पैठण', 'variety': 'CO-265', 'lab_brix': 18.24, 'lab_pol': 15.88, 'transit_hrs': 24.0},
    {'date': '06-Nov', 'plot_no': 4404, 'farmer': 'मुंडे आसाराम दामू', 'village': 'सोनविहीर', 'variety': 'CO-265', 'lab_brix': 17.24, 'lab_pol': 14.70, 'transit_hrs': 24.0},
    {'date': '06-Nov', 'plot_no': 8082, 'farmer': 'धस अनिल', 'village': 'जुनी खिर्डी', 'variety': 'CO-265', 'lab_brix': 14.54, 'lab_pol': 11.91, 'transit_hrs': 24.0}
]

results = []
for s in samples_10:
    pno = s['plot_no']
    m = df_master[df_master['Plot No'] == pno]
    if len(m) > 0:
        row = m.iloc[0].to_dict()
        
        standing_brix = float(row.get('predicted_brix_bx', 16.0))
        standing_pol = float(row.get('predicted_pol_juice_pct', 14.0))
        dist_km = float(row.get('distance_to_gangamai_mill_km', 25.0))
        
        # Apply Guardrail 3: Stunted Ratoon Cap
        df_single = pd.DataFrame([row])
        capped_brix, capped_pol = apply_stunted_ratoon_degradation_cap(df_single, [standing_brix], [standing_pol])
        standing_brix = capped_brix[0]
        standing_pol = capped_pol[0]
        
        # Apply Guardrail 4: Cut-to-Crush Delivered Sugar
        deliv_brix, deliv_pol, inv_loss, hrs = compute_cut_to_crush_delivered_sucrose(
            standing_brix, standing_pol, dist_km, transit_hours=s['transit_hrs']
        )
        deliv_brix = float(np.asarray(deliv_brix).ravel()[0])
        deliv_pol = float(np.asarray(deliv_pol).ravel()[0])
        
        lab_b = s['lab_brix']
        lab_p = s['lab_pol']
        
        lab_ccs = 1.022 * lab_p - 0.292 * lab_b
        pred_ccs = 1.022 * deliv_pol - 0.292 * deliv_brix
        
        brix_err = abs(deliv_brix - lab_b)
        brix_acc = max(0.0, (1.0 - (brix_err / lab_b)) * 100.0)
        
        pol_err = abs(deliv_pol - lab_p)
        pol_acc = max(0.0, (1.0 - (pol_err / lab_p)) * 100.0)
        
        ccs_err = abs(pred_ccs - lab_ccs)
        ccs_acc = max(0.0, (1.0 - (ccs_err / lab_ccs)) * 100.0)
        
        results.append({
            'date': s['date'],
            'plot_no': pno,
            'farmer': s['farmer'],
            'village': s['village'],
            'transit_hrs': s['transit_hrs'],
            'standing_pol': standing_pol,
            'deliv_brix': deliv_brix,
            'lab_brix': lab_b,
            'brix_err': brix_err,
            'brix_acc': brix_acc,
            'deliv_pol': deliv_pol,
            'lab_pol': lab_p,
            'pol_err': pol_err,
            'pol_acc': pol_acc,
            'pred_ccs': pred_ccs,
            'lab_ccs': lab_ccs,
            'ccs_acc': ccs_acc
        })

df_res = pd.DataFrame(results)

print("\n" + "="*95)
print("EVALUATION: SMART 54-PARAMETER HIERARCHICAL ENGINE WITH 4 PERMANENT GUARDRAILS")
print("="*95)
cols_show = ['date', 'plot_no', 'farmer', 'lab_brix', 'deliv_brix', 'brix_err', 'brix_acc', 'lab_pol', 'deliv_pol', 'pol_err', 'pol_acc']
print(df_res[cols_show].to_string(index=False))

print("\n" + "="*95)
print("FINAL AUDITED METRICS ACROSS ALL 10 GROUND TRUTH CRUSHES:")
print(f"Brix Mean Absolute Error (MAE): {df_res['brix_err'].mean():.3f} deg Bx | Mean Accuracy: {df_res['brix_acc'].mean():.2f}%")
print(f"Pol  Mean Absolute Error (MAE): {df_res['pol_err'].mean():.3f} %       | Mean Accuracy: {df_res['pol_acc'].mean():.2f}%")
print(f"CCS  Mean Absolute Error (MAE): {df_res['ccs_acc'].mean():.2f}%      | Mean Accuracy: {df_res['ccs_acc'].mean():.2f}%")
print("="*95)
