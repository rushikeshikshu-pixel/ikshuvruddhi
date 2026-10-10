import pickle
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

df = pd.read_csv('scratch/cane_lab_training_samples.csv')
df['plant_dt'] = pd.to_datetime(df['Plantation Date'], errors='coerce')
df['plant_year'] = df['plant_dt'].dt.year
df['plant_month'] = df['plant_dt'].dt.month
df['crop_age_days'] = pd.to_numeric(df['crop_age_days'], errors='coerce')
features = ['Cane Type', 'Variety Name', 'crop_age_days', 'plant_month', 'satellite_ndvi', 'satellite_ndre', 'satellite_ndwi', 'satellite_lswi', 'satellite_evi', 'canopy_occupancy_fraction', 'clear_sky_coverage_pct']
categorical = ['Cane Type', 'Variety Name']
numeric = [x for x in features if x not in categorical]
pre = ColumnTransformer([('cat', OneHotEncoder(handle_unknown='ignore'), categorical), ('num', SimpleImputer(strategy='median'), numeric)])
cv = KFold(n_splits=5, shuffle=True, random_state=42)
for target in ['lab_brix', 'lab_pol', 'lab_ccs']:
    model = Pipeline([('preprocess', pre), ('regressor', RandomForestRegressor(n_estimators=400, min_samples_leaf=3, max_features=0.8, random_state=42, n_jobs=1))])
    pred = cross_val_predict(model, df[features], df[target], cv=cv)
    err = pred - df[target]
    print(f'{target}: MAE={mean_absolute_error(df[target], pred):.3f}, RMSE={mean_squared_error(df[target], pred) ** 0.5:.3f}, bias={err.mean():+.3f}')
    model.fit(df[features], df[target])
    with open(f'models/lab_calibrated_{target[4:]}.pkl', 'wb') as f:
        pickle.dump({'pipeline': model, 'features': features, 'target': target, 'training_samples': len(df), 'source': 'cane sampale list.pdf'}, f)
print('Saved lab-calibrated models for Brix, Pol, and CCS.')
