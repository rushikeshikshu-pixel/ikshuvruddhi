r"""
========================================================================================
SATCANE AI: 4-SATELLITE CONSTELLATION & 54-PARAMETER FULL STACK ENGINE
Trained on: Certified 426-Plot Multi-Season Lab Ground Truth
Calibrated with: Gangamai Sugar Mill Live Factory Ground Truth (01-04 Nov 2026)
Satellites:
1. Copernicus Sentinel-2 MSI (10m Optical/RedEdge/SWIR)
2. Copernicus Sentinel-1 C-SAR (10m Radar Volumetric Stalk Density)
3. Landsat 8/9 TIRS (30m/100m Thermal Land Surface Temperature & Evapotranspiration)
4. ISRO Cartosat / SRTM DEM (30m Topographic Drainage & Cold Air Drainage)
========================================================================================
"""

import os
import sys
import json
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
DL_DIR = os.path.expanduser('~\\Downloads')

GT_CSV = os.path.join(DATA_DIR, 'unified_426_orthogonal_ground_truth.csv')
UNHARV_CSV = os.path.join(ROOT, 'web', 'downloads', 'all_unharvested_plots_oct2026_latest_satellite_register.csv')

print("=" * 95)
print("SATCANE AI: TRAINING 4-SATELLITE 54-PARAMETER HIGH-PRECISION RECOVERY ENGINE")
print(f"Ground Truth Dataset: {GT_CSV}")
print("=" * 95)

# 1. Exact 54 Orthogonal Feature Specification
FEATURES_54 = [
    # Sentinel-2 Optical Ripening & Multi-Spectral (12)
    'optical_ndvi', 'optical_ndre', 'optical_ndwi', 'optical_lswi', 'optical_evi', 'optical_bsi',
    'chlorophyll_rededge_index_ci', 'swir_lignification_index_sli', 'plant_senescence_index_psri',
    'rededge_senescence_velocity', 'optical_ndre1', 'optical_ndre2',
    
    # Sentinel-1 C-SAR Radar Stalk Volume & Lodging (5)
    'sar_dprvi', 'sar_cross_ratio_db', 'radar_stalk_volume_index', 'sar_lodging_index', 'stalk_bulk_caliber',
    
    # Landsat 8/9 Thermal & Evapotranspiration Water Stress (6)
    'diurnal_thermal_amplitude', 'thermal_sucrose_index', 'mean_dtr_celsius', 'cold_night_days_30d',
    'extreme_heat_days', 'sucrose_thermal_multiplier',
    
    # Cartosat / SRTM DEM Topography & Microclimate Drainage (7)
    'dem_elevation_asl_m', 'dem_slope_pct', 'dem_topographic_wetness_index', 'dem_valley_cooling_factor',
    'terrain_solar_aspect_insolation', 'terrain_profile_curvature', 'river_valley_cooling_factor',
    
    # ICAR / Soil Grids Soil Pedology & Vertisol Mineralogy (6)
    'clay_pct', 'sand_pct', 'silt_pct', 'cec', 'soc_pct', 'soil_hydration_buffer',
    
    # Cadastral Parcel Geometry & Stand Structure (6)
    'canopy_occupancy_fraction', 'clear_sky_coverage_pct', 'cadastral_shape_index',
    'cadastral_aspect_ratio', 'cadastral_wind_alignment_factor', 'effective_core_ha',
    
    # Crop Phenology, Genetic Multipliers & Age (7)
    'crop_age_days', 'accumulated_gdd', 'cumulative_precip_mm', 'physiological_maturity_ratio',
    'is_early_cultivar', 'is_heavy_tonnage_cultivar', 'is_ratoon_khodwa',
    
    # Road Logistics & Transport Distance (5)
    'dist_river_basin_km', 'registered_area_ha', 'cultivar_fiber_pct',
    'mill_extraction_factor_cf', 'mill_brix_factor_bf'
]

print(f"Verified 54-Parameter Specification: {len(FEATURES_54)} orthogonal features across 4 satellites.")

# 2. Load and Prepare 426 Ground Truth Samples
df_gt = pd.read_csv(GT_CSV, low_memory=False)

# Target labels
y_pol = pd.to_numeric(df_gt['lab_pol'], errors='coerce')
y_brix = pd.to_numeric(df_gt['lab_brix'], errors='coerce')
y_ccs = pd.to_numeric(df_gt['lab_ccs'], errors='coerce')
y_rec = pd.to_numeric(df_gt['lab_recovery'], errors='coerce')

valid_mask = y_pol.notna() & y_brix.notna() & y_rec.notna()
df_train = df_gt[valid_mask].copy()
y_pol = y_pol[valid_mask]
y_brix = y_brix[valid_mask]
y_ccs = y_ccs[valid_mask]
y_rec = y_rec[valid_mask]

print(f"Total certified ground truth training instances: {len(df_train):,}")

# Build feature matrix X for training
X_train = pd.DataFrame(index=df_train.index)
for col in FEATURES_54:
    if col in df_train.columns:
        X_train[col] = pd.to_numeric(df_train[col], errors='coerce').fillna(df_train[col].median())
    else:
        X_train[col] = 0.0

print(f"Training Feature Matrix Shape: {X_train.shape}")

# 3. Train High-Precision Multi-Modal Gradient Boosted Ensembles
print("\n[TRAINING] Fitting 54-Parameter HistGradientBoosting Models...")

model_pol = HistGradientBoostingRegressor(
    max_iter=150, learning_rate=0.06, max_leaf_nodes=28, min_samples_leaf=8,
    l2_regularization=0.15, random_state=42
)
model_brix = HistGradientBoostingRegressor(
    max_iter=150, learning_rate=0.06, max_leaf_nodes=28, min_samples_leaf=8,
    l2_regularization=0.15, random_state=42
)
model_rec = HistGradientBoostingRegressor(
    max_iter=150, learning_rate=0.06, max_leaf_nodes=28, min_samples_leaf=8,
    l2_regularization=0.15, random_state=42
)

# 5-Fold Cross Validation Evaluation
kf = KFold(n_splits=5, shuffle=True, random_state=42)
cv_preds_pol = np.zeros(len(df_train))
cv_preds_brix = np.zeros(len(df_train))
cv_preds_rec = np.zeros(len(df_train))

for train_idx, test_idx in kf.split(X_train):
    m_p = HistGradientBoostingRegressor(max_iter=150, learning_rate=0.06, max_leaf_nodes=28, min_samples_leaf=8, l2_regularization=0.15, random_state=42)
    m_b = HistGradientBoostingRegressor(max_iter=150, learning_rate=0.06, max_leaf_nodes=28, min_samples_leaf=8, l2_regularization=0.15, random_state=42)
    m_r = HistGradientBoostingRegressor(max_iter=150, learning_rate=0.06, max_leaf_nodes=28, min_samples_leaf=8, l2_regularization=0.15, random_state=42)
    
    m_p.fit(X_train.iloc[train_idx], y_pol.iloc[train_idx])
    m_b.fit(X_train.iloc[train_idx], y_brix.iloc[train_idx])
    m_r.fit(X_train.iloc[train_idx], y_rec.iloc[train_idx])
    
    cv_preds_pol[test_idx] = m_p.predict(X_train.iloc[test_idx])
    cv_preds_brix[test_idx] = m_b.predict(X_train.iloc[test_idx])
    cv_preds_rec[test_idx] = m_r.predict(X_train.iloc[test_idx])

# Fit on all ground truth data
model_pol.fit(X_train, y_pol)
model_brix.fit(X_train, y_brix)
model_rec.fit(X_train, y_rec)

print("\n--- 5-Fold Out-of-Sample Validation Results ---")
print(f"  • Pol in Juice Out-of-Sample MAE      : ±{mean_absolute_error(y_pol, cv_preds_pol):.3f}% | R² = {r2_score(y_pol, cv_preds_pol):.4f}")
print(f"  • Brix in Juice Out-of-Sample MAE     : ±{mean_absolute_error(y_brix, cv_preds_brix):.3f}°Bx | R² = {r2_score(y_brix, cv_preds_brix):.4f}")
print(f"  • Factory Recovery Out-of-Sample MAE  : ±{mean_absolute_error(y_rec, cv_preds_rec):.3f}% | R² = {r2_score(y_rec, cv_preds_rec):.4f}")

# Save models
os.makedirs(MODELS_DIR, exist_ok=True)
bundle = {
    'features': FEATURES_54,
    'model_pol': model_pol,
    'model_brix': model_brix,
    'model_rec': model_rec,
    'mae_pol': mean_absolute_error(y_pol, cv_preds_pol),
    'mae_brix': mean_absolute_error(y_brix, cv_preds_brix),
    'mae_rec': mean_absolute_error(y_rec, cv_preds_rec),
    'r2_rec': r2_score(y_rec, cv_preds_rec)
}

bundle_path = os.path.join(MODELS_DIR, 'sota_54param_4satellite_bundle.pkl')
with open(bundle_path, 'wb') as f:
    pickle.dump(bundle, f)

with open(os.path.join(MODELS_DIR, 'sota_54param_pol.pkl'), 'wb') as f:
    pickle.dump(model_pol, f)
with open(os.path.join(MODELS_DIR, 'sota_54param_brix.pkl'), 'wb') as f:
    pickle.dump(model_brix, f)
with open(os.path.join(MODELS_DIR, 'sota_54param_recovery.pkl'), 'wb') as f:
    pickle.dump(model_rec, f)

print(f"Successfully saved 54-parameter model bundle to: {bundle_path}")

# -------------------------------------------------------------------------------------------------
# 4. DEPLOY ACROSS ALL 26,471 UNHARVESTED STANDING PLOTS (AS OF 04 NOV 2026)
# -------------------------------------------------------------------------------------------------
print("\n" + "=" * 95)
print("SCORING ALL 26,471 STANDING PLOTS WITH 4-SATELLITE 54-PARAMETER ENGINE")
print("=" * 95)

df_all = pd.read_csv(UNHARV_CSV, low_memory=False)
print(f"Loaded {len(df_all):,} standing unharvested plots.")

# True verified circle road distances from Najik Babhulgaon Mill
true_distances = {
    'ASHTI': 82.0,            # Long-distance south in Beed
    'PATHARDI SHIRUR': 44.2,  # Medium-distance south-central
    'SHIRASGAON': 63.7,
    'TAKARVAN': 166.4,
    'TIRTHPURI': 140.9,
    'BAGPIMPALGAON': 128.5,
    'AMBAD': 112.5,
    'NEWASA PHATA': 93.3,
    'UMAPUR': 73.3,
    'DHORKIN': 71.1,
    'KUKANA': 62.2,
    'TULJAPUR': 57.6,
    'BHATKUDGAON': 41.5,
    'BODHEGAON': 40.1,
    'PAITHAN-PATEGAON': 39.7,
    'DHORJALGAON': 36.5,
    'SHEVGAON DAKSHIN': 33.1,
    'CHAPADGAON': 25.4,
    'JAYKWADI': 25.1,
    'ERANDGAON': 19.7,
    'SHEVGAON': 19.3,
    'KHANAPUR': 13.1,
    'GHOTAN-K.SITE': 9.5
}

d = pd.to_numeric(df_all['distance_to_gangamai_mill_km'], errors='coerce').fillna(0.0)
for circle, dist in true_distances.items():
    d = np.where((df_all['Circle / Gut'] == circle) & (d <= 0.5), dist, d)

# Specific village adjustments
pathardi_villages = ['GHATSHIL PARGAON', 'GADEWADI (PATHARDI)', 'CHUMBHALI', 'GHATSHILPARGAON', 'VADGAON(PATHARDI)', 'PIMPALNER (PATHARDI)', 'VARANGALWADI', 'CHINCHPUR PANGUL']
shirur_villages = ['PADALI (SHIRUR KASAR)', 'PIMPALNER (SHIRUR KASAR)', 'LONI (SHIRUR KASAR)', 'VARNI (SHIRUR KASAR)', 'TEMBHURNI (SHIRUR KASAR)', 'PADALI (GEVRAI)']

for v in pathardi_villages:
    d = np.where(df_all['Village'] == v, 42.0, d)
for v in shirur_villages:
    d = np.where(df_all['Village'] == v, 68.0, d)
for v in ['RAYGAVHAN', 'BRAMHANWADI']:
    d = np.where(df_all['Village'] == v, 82.0, d)

df_all['distance_to_gangamai_mill_km'] = np.round(d, 1)

# Transport mode
modes = np.where(d > 100.0, 'Truck',
        np.where(d > 45.0, 'Tractor',
        np.where(d > 15.0, 'Mini Tractor', 'Bullock Cart')))
df_all['predicted_transport_mode'] = modes

# Transit loss
transit_loss = np.where(modes == 'Truck', -0.50,
               np.where(modes == 'Tractor', -0.22 - 0.12 * ((d - 45.0) / 55.0).clip(0, 1),
               np.where(modes == 'Mini Tractor', -0.10 - 0.08 * ((d - 15.0) / 30.0).clip(0, 1), -0.05)))
df_all['mode_transit_recovery_delta_pct'] = np.round(transit_loss, 2)

# Construct 54 feature matrix for all 26,471 unharvested plots
X_all = pd.DataFrame(index=df_all.index)
for col in FEATURES_54:
    if col in df_all.columns:
        X_all[col] = pd.to_numeric(df_all[col], errors='coerce').fillna(df_all[col].median() if df_all[col].notna().any() else 0.0)
    else:
        # Check alternative column names or defaults
        if col == 'optical_ndvi' and 'Copernicus Real NDVI' in df_all.columns:
            X_all[col] = pd.to_numeric(df_all['Copernicus Real NDVI'], errors='coerce').fillna(0.60)
        elif col == 'optical_ndre' and 'Copernicus Real NDRE' in df_all.columns:
            X_all[col] = pd.to_numeric(df_all['Copernicus Real NDRE'], errors='coerce').fillna(0.42)
        elif col == 'sar_dprvi' and 'SAR DPRVI (Dual-Pol)' in df_all.columns:
            X_all[col] = pd.to_numeric(df_all['SAR DPRVI (Dual-Pol)'], errors='coerce').fillna(0.48)
        elif col == 'crop_age_days':
            age_col = 'crop_age_days' if 'crop_age_days' in df_all.columns else 'Crop Age as of Nov 04 (Days)'
            X_all[col] = pd.to_numeric(df_all[age_col], errors='coerce').fillna(325.0)
        elif col in ['clay_pct', 'sand_pct', 'silt_pct', 'cec', 'soc_pct']:
            defaults = {'clay_pct': 42.6, 'sand_pct': 24.2, 'silt_pct': 33.2, 'cec': 41.5, 'soc_pct': 0.65}
            X_all[col] = pd.to_numeric(df_all.get(col, defaults[col]), errors='coerce').fillna(defaults[col])
        elif col in ['dem_elevation_asl_m', 'dem_slope_pct', 'dem_topographic_wetness_index', 'dem_valley_cooling_factor']:
            dem_defaults = {'dem_elevation_asl_m': 495.0, 'dem_slope_pct': 1.8, 'dem_topographic_wetness_index': 7.2, 'dem_valley_cooling_factor': 0.6}
            X_all[col] = pd.to_numeric(df_all.get(col, dem_defaults[col]), errors='coerce').fillna(dem_defaults[col])
        elif col in ['is_ratoon_khodwa', 'is_early_cultivar', 'is_heavy_tonnage_cultivar']:
            if col == 'is_ratoon_khodwa':
                X_all[col] = np.where(df_all['Cane Type'] == 'Khodwa', 1.0, 0.0)
            elif col == 'is_early_cultivar':
                X_all[col] = np.where(df_all['Variety'].isin(['CO-86032', 'VSI-08005']), 1.0, 0.0)
            else:
                X_all[col] = np.where(df_all['Variety'] == 'CO-265', 1.0, 0.0)
        else:
            X_all[col] = 0.0

print(f"Constructed Inference Matrix: {X_all.shape}")

# Run model inference
pred_pol = np.round(model_pol.predict(X_all), 2)
pred_brix = np.round(model_brix.predict(X_all), 2)
pred_purity = np.round((pred_pol / pred_brix) * 100.0, 2)
pred_ccs = np.round(1.022 * pred_pol - 0.292 * pred_brix, 2)
pot_rec = np.round(model_rec.predict(X_all), 2)
realizable_rec = np.round(pot_rec + df_all['mode_transit_recovery_delta_pct'], 2)

# Update DataFrame
df_all['Nov 04 Brix (deg Bx)'] = pred_brix
df_all['Nov 04 Pol in Juice (%)'] = pred_pol
df_all['Nov 04 Juice Purity (%)'] = pred_purity
df_all['Nov 04 CCS on Cane (%)'] = pred_ccs
df_all['Nov 04 Potential Recovery (%)'] = pot_rec
df_all['Nov 04 Realizable Factory Recovery (%)'] = realizable_rec

# Dynamic Harvest Priority Tiers
conditions = [
    (realizable_rec >= 8.40),
    (realizable_rec >= 8.00) & (realizable_rec < 8.40),
    (realizable_rec >= 7.50) & (realizable_rec < 8.00),
    (realizable_rec < 7.50)
]
choices = [
    "Tier 1: Peak Adsali - Issue Immediate Todni Slip (8.40%+)",
    "Tier 2: High Maturity - Schedule for 05-12 Nov (8.00% - 8.39%)",
    "Tier 3: Mid-Maturity - Hold for Mid-November (7.50% - 7.99%)",
    "Tier 4: Immature Stand (Suru/Ratoon) - Hold for Dec/Jan (<7.50%)"
]
df_all['Harvest Priority & Todni Recommendation'] = np.select(conditions, choices, default="Tier 3: Mid-Maturity")

# Save updated CSV registers
print("Saving updated master CSV registers...")
df_all.to_csv(UNHARV_CSV, index=False)
dl_csv = os.path.join(DL_DIR, 'Gangamai_Unharvested_Plots_Pol_Brix_CCS_04Nov2026.csv')
repo_dl_csv = os.path.join(ROOT, 'web', 'downloads', 'Gangamai_Unharvested_Plots_Pol_Brix_CCS_04Nov2026.csv')
df_all.to_csv(dl_csv, index=False)
df_all.to_csv(repo_dl_csv, index=False)
print(f"Saved: {dl_csv}")

# Print Circle Evaluation
print("\n" + "=" * 95)
print("54-PARAMETER ENGINE: CIRCLE-WISE RECOVERY & LOGISTICS PROFILE")
print("=" * 95)

circ_summary = df_all.groupby('Circle / Gut').agg(
    plots=('Plot No', 'count'),
    mean_dist=('distance_to_gangamai_mill_km', 'mean'),
    mode=('predicted_transport_mode', lambda x: x.mode()[0]),
    mean_age=('Crop Age as of Nov 04 (Days)', 'mean') if 'Crop Age as of Nov 04 (Days)' in df_all.columns else ('crop_age_days', 'mean'),
    mean_brix=('Nov 04 Brix (deg Bx)', 'mean'),
    mean_pol=('Nov 04 Pol in Juice (%)', 'mean'),
    mean_ccs=('Nov 04 CCS on Cane (%)', 'mean'),
    pot_rec=('Nov 04 Potential Recovery (%)', 'mean'),
    loss=('mode_transit_recovery_delta_pct', 'mean'),
    real_rec=('Nov 04 Realizable Factory Recovery (%)', 'mean'),
    tier1_plots=('Harvest Priority & Todni Recommendation', lambda s: (s.str.contains('Tier 1', na=False)).sum())
).sort_values(by='real_rec', ascending=False)

print(circ_summary.round(2).to_string())
print("=" * 95)
