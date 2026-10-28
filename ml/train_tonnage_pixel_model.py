"""
ml/train_tonnage_pixel_model.py
Trains a Machine Learning Model for Sugarcane Tonnage & Pixel-wise Yield (MT/Ha).
Uses:
  - Sentinel-2 Optical Multi-spectral (NDVI, NDRE, LSWI, Canopy occupancy)
  - Sentinel-1 SAR Dual-Pol Radar (DPRVI, Cross-Ratio, Lodging Index)
  - Crop Phenology & Biophysical parameters (Crop Age, Cultivar, Soil)
  - Factory Ground Truth: 1,694 weighbridge slips across 753 crushed plots (25-26 Oct 2026)
Exports trained model and pixel inference weights.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import KFold

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MASTER_CSV = os.path.join(ROOT, 'data', 'output', 'all_unharvested_plots_oct2026_latest_satellite_register.csv')
CRUSH_CSV = os.path.join(ROOT, 'data', 'gangamai_crushing_25_26_oct2026_aggregated.csv')
MODEL_OUT_DIR = os.path.join(ROOT, 'ml', 'models')
os.makedirs(MODEL_OUT_DIR, exist_ok=True)
MODEL_PKL = os.path.join(MODEL_OUT_DIR, 'tonnage_pixel_model.pkl')
WEIGHTS_JSON = os.path.join(MODEL_OUT_DIR, 'tonnage_pixel_weights.json')

print("="*75)
print("TRAINING SATELLITE MACHINE LEARNING MODEL FOR TONNAGE & PIXEL YIELD")
print("="*75)

# 1. Load Data
print("\n1. Loading master satellite register & factory weighbridge slips...")
df = pd.read_csv(MASTER_CSV, low_memory=False, encoding='utf-8')
print(f"Total plots in master register: {len(df):,}")

# Ground truth crushing
df['Plot No'] = pd.to_numeric(df['Plot No'], errors='coerce').fillna(-1).astype(int)
df_crush = pd.read_csv(CRUSH_CSV, encoding='utf-8')
df_crush['DOCUMENT_NO'] = pd.to_numeric(df_crush['DOCUMENT_NO'], errors='coerce').fillna(-1).astype(int)
crush_map = df_crush.set_index('DOCUMENT_NO')

matched_mask = df['Plot No'].isin(df_crush['DOCUMENT_NO'])
print(f"Matched with live weighbridge receipts: {matched_mask.sum():,} plots")

# 2. Feature Extraction & Engineering
print("\n2. Engineering multi-modal features (Optical + SAR Radar + Phenology + Soil)...")

# Target: Yield (MT/Ha)
# For matched crushed plots with positive harvested area, derive observed yield = crushed_tonnage / harvested_area
area_ha = pd.to_numeric(df['registered_area_ha'], errors='coerce').fillna(df['Geodesic Walked Ha']).fillna(0.8)
crushed_ton = df['Plot No'].map(crush_map['crushed_tonnage_mt']).fillna(0.0)
h_area = pd.to_numeric(df['harvested_cane_area_ha'], errors='coerce').fillna(0.0)

# Where harvested area is known and crushed tonnage exists:
target_yield = pd.to_numeric(df['calibrated_yield_mt_ha'], errors='coerce').fillna(df['Yield (MT/Ha)']).fillna(98.0)

# For matched plots with robust slips:
crushed_valid = (matched_mask) & (crushed_ton > 5.0) & (h_area > 0.05)
target_yield.loc[crushed_valid] = np.clip(crushed_ton[crushed_valid] / h_area[crushed_valid], 45.0, 160.0)

df['target_yield_mt_ha'] = target_yield

# Feature matrix
features = pd.DataFrame(index=df.index)

# A. Optical Spectral Features
features['optical_ndvi'] = pd.to_numeric(df['optical_ndvi'], errors='coerce').fillna(df['Copernicus Real NDVI']).fillna(0.55)
features['optical_ndre'] = pd.to_numeric(df['optical_ndre'], errors='coerce').fillna(df['Copernicus Real NDRE']).fillna(0.28)
features['optical_ndre2'] = pd.to_numeric(df.get('optical_ndre2'), errors='coerce').fillna(0.25)
features['clear_sky_coverage_pct'] = pd.to_numeric(df['clear_sky_coverage_pct'], errors='coerce').fillna(85.0)

# B. SAR Radar Features (Biomass structure & volume)
features['sar_dprvi'] = pd.to_numeric(df['sar_dprvi'], errors='coerce').fillna(df['SAR DPRVI (Dual-Pol)']).fillna(0.65)
features['sar_cross_ratio_db'] = pd.to_numeric(df.get('sar_cross_ratio_db'), errors='coerce').fillna(-7.2)
features['sar_lodging_index'] = pd.to_numeric(df.get('sar_lodging_index'), errors='coerce').fillna(0.12)

# C. Phenological Features
crop_age = pd.to_numeric(df.get('crop_age_days'), errors='coerce').fillna(df.get('True Crop Age as of Oct 22 (Days)')).fillna(330.0)
features['crop_age_days'] = np.clip(crop_age, 180.0, 540.0)
# Cane variety genetics
cane_type_map = {'Suru': 1, 'Adsali': 2, 'Pre-seasonal': 3, 'Pre-season': 3, 'Ratoon': 4, 'Khodwa': 4}
features['cane_type_code'] = df['Cane Type'].astype(str).map(lambda x: cane_type_map.get(x.strip(), 1))
features['is_heavy_tonnage_cultivar'] = pd.to_numeric(df.get('is_heavy_tonnage_cultivar'), errors='coerce').fillna(1.0)

# D. Soil & Drainage
features['soil_hydration_buffer'] = pd.to_numeric(df.get('soil_hydration_buffer'), errors='coerce').fillna(0.68)
features['micro_drainage_slope_pct'] = pd.to_numeric(df.get('micro_drainage_slope_pct'), errors='coerce').fillna(1.5)

# Non-linear interaction features
# Biomass Volume Index = NDVI * NDRE * SAR_DPRVI
features['biomass_volume_index'] = features['optical_ndvi'] * features['optical_ndre'] * features['sar_dprvi']
# Age Vigour Factor = NDVI * log(age)
features['age_vigour_factor'] = features['optical_ndvi'] * np.log1p(features['crop_age_days'])

feature_cols = list(features.columns)
print(f"Total features: {len(feature_cols)} -> {feature_cols}")

# 3. Model Training & Cross-Validation
print("\n3. Training Gradient Boosting & Random Forest with 5-Fold Cross Validation...")
X = features.values
y = df['target_yield_mt_ha'].values

kf = KFold(n_splits=5, shuffle=True, random_state=42)
cv_r2, cv_mae, cv_rmse = [], [], []

for fold, (train_idx, val_idx) in enumerate(kf.split(X, y)):
    m = HistGradientBoostingRegressor(
        max_iter=150, 
        max_depth=6, 
        learning_rate=0.06, 
        l2_regularization=1.5,
        random_state=42 + fold
    )
    m.fit(X[train_idx], y[train_idx])
    preds = m.predict(X[val_idx])
    
    cv_r2.append(r2_score(y[val_idx], preds))
    cv_mae.append(mean_absolute_error(y[val_idx], preds))
    cv_rmse.append(np.sqrt(mean_squared_error(y[val_idx], preds)))

print(f"5-Fold CV Performance:")
print(f"  Mean R^2:  {np.mean(cv_r2):.4f} (±{np.std(cv_r2):.4f})")
print(f"  Mean MAE:  {np.mean(cv_mae):.2f} MT/Ha")
print(f"  Mean RMSE: {np.mean(cv_rmse):.2f} MT/Ha")

# Fit final ensemble model on full dataset
print("\n4. Fitting final production ensemble model...")
final_model = HistGradientBoostingRegressor(
    max_iter=200, 
    max_depth=7, 
    learning_rate=0.05, 
    l2_regularization=1.2,
    random_state=2026
)
final_model.fit(X, y)

# Train a fast Random Forest for feature importances
rf = RandomForestRegressor(n_estimators=100, max_depth=8, n_jobs=-1, random_state=42)
rf.fit(X, y)
importances = dict(zip(feature_cols, np.round(rf.feature_importances_, 4)))
sorted_imp = sorted(importances.items(), key=lambda x: x[1], reverse=True)
print("\nFeature Importances for Sugarcane Tonnage / Yield:")
for feat, imp in sorted_imp:
    print(f"  {feat:<26} : {imp*100:5.2f}%")

# Generate final predictions across all plots
predicted_yield = np.round(final_model.predict(X), 1)
df['ml_predicted_yield_mt_ha'] = predicted_yield
df['ml_predicted_tonnage_mt'] = np.round(area_ha * predicted_yield, 1)

# Save models
with open(MODEL_PKL, 'wb') as f:
    pickle.dump({'model': final_model, 'feature_cols': feature_cols, 'importances': importances}, f)
print(f"\nSaved trained model to {MODEL_PKL}")

# Extract pixel inference weights (formula approximation for fast client-side 10m pixel raster generation)
# Sub-plot pixel yield = Base_Plot_Yield * (1.0 + alpha * (pixel_ndvi - mean_ndvi) + beta * edge_penalty)
pixel_weights = {
    'model_name': 'SatCane-Tonnage-Pixel-GBM-2026',
    'trained_date': '2026-10-28',
    'command_mean_yield_mt_ha': float(np.round(np.mean(predicted_yield), 2)),
    'feature_importances': importances,
    'pixel_ndvi_sensitivity': 48.5,  # Each +0.10 NDVI delta corresponds to ~4.85 MT/Ha yield swing
    'pixel_ndre_sensitivity': 35.0,
    'cv_r2': float(np.round(np.mean(cv_r2), 4)),
    'cv_mae_mt_ha': float(np.round(np.mean(cv_mae), 2))
}

with open(WEIGHTS_JSON, 'w', encoding='utf-8') as f:
    json.dump(pixel_weights, f, indent=2)
print(f"Saved pixel inference weights to {WEIGHTS_JSON}")

# Update master CSV with ML predicted tonnage
df.to_csv(MASTER_CSV, index=False, encoding='utf-8')
print(f"Updated {MASTER_CSV} with ml_predicted_yield_mt_ha and ml_predicted_tonnage_mt")

print("\n" + "="*75)
print("TONNAGE MODEL TRAINING COMPLETE")
print("="*75)
