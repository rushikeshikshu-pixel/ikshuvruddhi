r"""
========================================================================================
RETRAIN SATCANE AI ENGINE WITH AUTHENTIC 05-NOV-2026 PHYSICAL LAB SAMPLE TESTS
Matched to True Farmers & Tyre Gadi Numbers from Slip:
1. Gadi 57:  गुजर अंबादास भानुदास (Erandgaon, Plot 2685)  | Brix 14.98 | Pol 12.10
2. Gadi 218: खेडकर अशोक बाबुराव (Ghotan, Plot 16558)     | Brix 14.28 | Pol 12.02
3. Gadi 685: भराट खंडू उत्तम (Ravtale, Plot 3755)        | Brix 15.29 | Pol 12.50
4. Gadi 62:  गुजर अंबादास भानुदास [2] (Erandgaon, Plot 2684)| Brix 14.54 | Pol 11.84
5. Gadi 723: क्षिरसागर बाळासाहेब किसन (Ghotan, Plot 13509)| Brix 15.78 | Pol 12.58

Cut Time: 03:00 AM - 05:00 AM on 05 Nov 2026
Crush Time: 02:00 PM on 05 Nov 2026 (10-Hour Staling & Transit Delay)
========================================================================================
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import mean_absolute_error, r2_score

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(ROOT, 'data')
MODELS_DIR = os.path.join(ROOT, 'models')

print("=" * 95)
print("SATCANE AI: INGESTING 05-NOV-2026 TRUE FARMER GROUND TRUTH & RETRAINING")
print("=" * 95)

# 1. 05 Nov 2026 Lab Samples matched to True Farmer Plots
true_samples = [
    {'plot_no': 2685, 'gadi_no': 57, 'farmer': 'गुजर अंबादास भानुदास', 'village': 'एरंडगाव', 'variety': 'CO-265', 'lab_brix': 14.98, 'lab_pol': 12.10, 'cut_time': '04:00 AM', 'delay_hrs': 10.0},
    {'plot_no': 16558, 'gadi_no': 218, 'farmer': 'खेडकर अशोक बाबुराव', 'village': 'घोटन (भारत वस्ती)', 'variety': 'CO-265', 'lab_brix': 14.28, 'lab_pol': 12.02, 'cut_time': '04:00 AM', 'delay_hrs': 10.0},
    {'plot_no': 3755, 'gadi_no': 685, 'farmer': 'भराट खंडू उत्तम', 'village': 'रावताळे (भारत वस्ती)', 'variety': 'CO-265', 'lab_brix': 15.29, 'lab_pol': 12.50, 'cut_time': '03:30 AM', 'delay_hrs': 10.5},
    {'plot_no': 2684, 'gadi_no': 62, 'farmer': 'गुजर अंबादास भानुदास (२री गाडी)', 'village': 'एरंडगाव', 'variety': 'VSI 18121', 'lab_brix': 14.54, 'lab_pol': 11.84, 'cut_time': '04:30 AM', 'delay_hrs': 9.5},
    {'plot_no': 13509, 'gadi_no': 723, 'farmer': 'क्षिरसागर बाळासाहेब किसन', 'village': 'घोटन (टाका मळा)', 'variety': 'CO-265', 'lab_brix': 15.78, 'lab_pol': 12.58, 'cut_time': '03:00 AM', 'delay_hrs': 11.0}
]

# 2. 54-Parameter Feature Specification
FEATURES_54 = [
    'optical_ndvi', 'optical_ndre', 'optical_ndwi', 'optical_lswi', 'optical_evi', 'optical_bsi',
    'chlorophyll_rededge_index_ci', 'swir_lignification_index_sli', 'plant_senescence_index_psri',
    'rededge_senescence_velocity', 'optical_ndre1', 'optical_ndre2',
    'sar_dprvi', 'sar_cross_ratio_db', 'radar_stalk_volume_index', 'sar_lodging_index', 'stalk_bulk_caliber',
    'diurnal_thermal_amplitude', 'thermal_sucrose_index', 'mean_dtr_celsius', 'cold_night_days_30d',
    'extreme_heat_days', 'sucrose_thermal_multiplier',
    'dem_elevation_asl_m', 'dem_slope_pct', 'dem_topographic_wetness_index', 'dem_valley_cooling_factor',
    'terrain_solar_aspect_insolation', 'terrain_profile_curvature', 'river_valley_cooling_factor',
    'clay_pct', 'sand_pct', 'silt_pct', 'cec', 'soc_pct', 'soil_hydration_buffer',
    'canopy_occupancy_fraction', 'clear_sky_coverage_pct', 'cadastral_shape_index',
    'cadastral_aspect_ratio', 'cadastral_wind_alignment_factor', 'effective_core_ha',
    'crop_age_days', 'accumulated_gdd', 'cumulative_precip_mm', 'physiological_maturity_ratio',
    'is_early_cultivar', 'is_heavy_tonnage_cultivar', 'is_ratoon_khodwa',
    'dist_river_basin_km', 'registered_area_ha', 'cultivar_fiber_pct',
    'mill_extraction_factor_cf', 'mill_brix_factor_bf'
]

# 3. Load Real Multi-Satellite Features from Register
UNH_CSV = os.path.join(ROOT, 'web', 'downloads', 'all_unharvested_plots_oct2026_latest_satellite_register.csv')
df_unh = pd.read_csv(UNH_CSV, low_memory=False)

nov05_rows = []
for s in true_samples:
    plot_row = df_unh[df_unh['Plot No'] == s['plot_no']].iloc[0]
    row = {f: plot_row[f] for f in FEATURES_54 if f in plot_row}
    row['lab_brix'] = s['lab_brix']
    row['lab_pol'] = s['lab_pol']
    row['lab_purity'] = round(s['lab_pol'] / s['lab_brix'] * 100.0, 2)
    row['lab_ccs'] = round(1.022 * s['lab_pol'] - 0.292 * s['lab_brix'], 3)
    row['lab_recovery'] = round(row['lab_ccs'] * 0.804, 3)
    row['sample_id'] = '05NOV_GADI_' + str(s['gadi_no'])
    row['farmer_name'] = s['farmer']
    row['village'] = s['village']
    row['plot_no'] = s['plot_no']
    row['cut_time'] = s['cut_time']
    row['delay_hrs'] = s['delay_hrs']
    row['reconstructed_field_pol'] = round(s['lab_pol'] + (s['delay_hrs'] - 4.0) * 0.05 + 0.10, 2)
    row['reconstructed_field_brix'] = round(s['lab_brix'] + 0.35, 2)
    row['sample_date'] = '2026-11-05'
    row['lab_year'] = '2026-27 In-Season Spot Check'
    nov05_rows.append(row)

df_05nov = pd.DataFrame(nov05_rows)

print("Ingested 5 Authentic Physical Lab Samples:")
for idx, r in df_05nov.iterrows():
    print(f"  • {r['sample_id']} | {r['farmer_name']} ({r['village']}) | Plot {r['plot_no']} | Lab Brix: {r['lab_brix']}°Bx | Lab Pol: {r['lab_pol']}% | Reconstructed Field Pol: {r['reconstructed_field_pol']}%")

# 4. Load Master Ground Truth Dataset
gt_path = os.path.join(DATA_DIR, 'unified_809_orthogonal_ground_truth.csv')
df_gt = pd.read_csv(gt_path, low_memory=False)
print(f"\nExisting Certified Master Ground Truth: {len(df_gt)} records")

# Combine into master 814 ground truth
df_combined = pd.concat([df_gt, df_05nov], ignore_index=True, sort=False)
valid_mask = df_combined['lab_pol'].notna() & df_combined['lab_brix'].notna() & df_combined['lab_recovery'].notna()
df_combined = df_combined[valid_mask].copy()

total_samples = len(df_combined)
print(f"Total Master Ground Truth Records after Ingestion: {total_samples}")

# Build feature matrix X
X = pd.DataFrame(index=df_combined.index)
for col in FEATURES_54:
    if col in df_combined.columns:
        s = pd.to_numeric(df_combined[col], errors='coerce')
        X[col] = s.fillna(s.median() if not np.isnan(s.median()) else 0.0)
    else:
        X[col] = 0.0

y_pol = pd.to_numeric(df_combined['lab_pol'], errors='coerce')
y_brix = pd.to_numeric(df_combined['lab_brix'], errors='coerce')
y_rec = pd.to_numeric(df_combined['lab_recovery'], errors='coerce')

# 5. Perform 5-Fold Cross Validation
kf = KFold(n_splits=5, shuffle=True, random_state=42)
pol_maes, brix_maes, rec_maes = [], [], []
pol_r2s, brix_r2s, rec_r2s = [], [], []

for fold, (trn_idx, val_idx) in enumerate(kf.split(X), 1):
    X_tr, y_tr_pol, y_tr_bx, y_tr_rec = X.iloc[trn_idx], y_pol.iloc[trn_idx], y_brix.iloc[trn_idx], y_rec.iloc[trn_idx]
    X_va, y_va_pol, y_va_bx, y_va_rec = X.iloc[val_idx], y_pol.iloc[val_idx], y_brix.iloc[val_idx], y_rec.iloc[val_idx]
    
    m_pol = HistGradientBoostingRegressor(max_iter=150, max_leaf_nodes=31, min_samples_leaf=15, l2_regularization=1.5, random_state=42)
    m_pol.fit(X_tr, y_tr_pol)
    p_pol = m_pol.predict(X_va)
    
    m_bx = HistGradientBoostingRegressor(max_iter=150, max_leaf_nodes=31, min_samples_leaf=15, l2_regularization=1.5, random_state=42)
    m_bx.fit(X_tr, y_tr_bx)
    p_bx = m_bx.predict(X_va)
    
    m_rec = HistGradientBoostingRegressor(max_iter=150, max_leaf_nodes=31, min_samples_leaf=15, l2_regularization=1.5, random_state=42)
    m_rec.fit(X_tr, y_tr_rec)
    p_rec = m_rec.predict(X_va)
    
    pol_maes.append(mean_absolute_error(y_va_pol, p_pol))
    pol_r2s.append(r2_score(y_va_pol, p_pol))
    brix_maes.append(mean_absolute_error(y_va_bx, p_bx))
    brix_r2s.append(r2_score(y_va_bx, p_bx))
    rec_maes.append(mean_absolute_error(y_va_rec, p_rec))
    rec_r2s.append(r2_score(y_va_rec, p_rec))

print("\n" + "=" * 95)
print(f"RETRAINED MODEL PERFORMANCE ACROSS {total_samples} CERTIFIED SAMPLES:")
print(f"Recovery (CCS) Out-of-Sample MAE: +/-{np.mean(rec_maes):.4f}% (R2 = {np.mean(rec_r2s):.4f})")
print(f"Pol in Juice Out-of-Sample MAE:   +/-{np.mean(pol_maes):.4f}% (R2 = {np.mean(pol_r2s):.4f})")
print(f"Brix Out-of-Sample MAE:           +/-{np.mean(brix_maes):.4f} deg Bx (R2 = {np.mean(brix_r2s):.4f})")
print("=" * 95)

# 6. Fit and Save Final Production Models
final_pol = HistGradientBoostingRegressor(max_iter=200, max_leaf_nodes=31, min_samples_leaf=15, l2_regularization=1.5, random_state=42)
final_pol.fit(X, y_pol)

final_bx = HistGradientBoostingRegressor(max_iter=200, max_leaf_nodes=31, min_samples_leaf=15, l2_regularization=1.5, random_state=42)
final_bx.fit(X, y_brix)

final_rec = HistGradientBoostingRegressor(max_iter=200, max_leaf_nodes=31, min_samples_leaf=15, l2_regularization=1.5, random_state=42)
final_rec.fit(X, y_rec)

os.makedirs(MODELS_DIR, exist_ok=True)
with open(os.path.join(MODELS_DIR, 'sota_54param_pol.pkl'), 'wb') as f:
    pickle.dump(final_pol, f)
with open(os.path.join(MODELS_DIR, 'sota_54param_brix.pkl'), 'wb') as f:
    pickle.dump(final_bx, f)
with open(os.path.join(MODELS_DIR, 'sota_54param_recovery.pkl'), 'wb') as f:
    pickle.dump(final_rec, f)

bundle = {
    'features': FEATURES_54,
    'model_pol': final_pol,
    'model_brix': final_bx,
    'model_recovery': final_rec,
    'training_samples': total_samples,
    'cv_recovery_r2': float(np.mean(rec_r2s)),
    'cv_recovery_mae': float(np.mean(rec_maes)),
    'nov05_true_farmer_calibration': {
        'farmers': [s['farmer'] for s in true_samples],
        'plots': [s['plot_no'] for s in true_samples],
        'transit_delay_hours': 10.0,
        'transit_inversion_loss_pct': 0.45
    }
}
with open(os.path.join(MODELS_DIR, 'sota_54param_4satellite_bundle.pkl'), 'wb') as f:
    pickle.dump(bundle, f)

df_combined.to_csv(os.path.join(DATA_DIR, 'unified_814_orthogonal_ground_truth.csv'), index=False)
df_05nov.to_csv(os.path.join(DATA_DIR, 'gangamai_05nov2026_physical_spot_checks.csv'), index=False)
print("Saved retrained models, metadata bundle, and CSVs successfully.")
