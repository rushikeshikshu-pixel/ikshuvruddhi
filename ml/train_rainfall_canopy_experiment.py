import requests, pandas as pd, numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

df=pd.read_csv('scratch/cane_lab_samples_sept2026.csv'); df['sample_date']=pd.to_datetime(df['sample_date'])
sat=pd.read_csv('scratch/cane_lab_date_matched_samples.csv')
df=df.drop(columns=[c for c in sat.columns if c in df.columns and c not in ['Plot No']]).merge(sat, on='Plot No', suffixes=('', '_sat'))
df['sample_date']=pd.Timestamp('2026-09-25')
print('sample date range:', df['sample_date'].min().date(), 'to', df['sample_date'].max().date())
def rain(lat,lon,end):
    start=(end-pd.Timedelta(days=60)).strftime('%Y%m%d'); end_s=end.strftime('%Y%m%d')
    url=f'https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR&community=AG&longitude={lon}&latitude={lat}&start={start}&end={end_s}&format=JSON'
    try:
        vals=pd.Series(requests.get(url,timeout=30).json()['properties']['parameter']['PRECTOTCORR'],dtype=float)
        out={f'rain_{w}d':round(float(vals.tail(w).sum()),2) for w in [7,14,30,60]}; out['rain_events_30d']=int((vals.tail(30)>=5).sum()); out['dry_days_14d']=int((vals.tail(14)<1).sum()); return out
    except Exception as e:
        print('rainfall failed',e); out={f'rain_{w}d':np.nan for w in [7,14,30,60]}; out.update({'rain_events_30d':np.nan,'dry_days_14d':np.nan}); return out
rows=[]
for i,r in df.iterrows(): rows.append(rain(r['Lat 1'],r['Long 1'],r['sample_date'])); print(f'{i+1}/{len(df)} rainfall',flush=True)
df=pd.concat([df.reset_index(drop=True),pd.DataFrame(rows)],axis=1)
df['canopy_growth_proxy']=(0.5*df['matched_ndre'].fillna(df['satellite_ndre'])+0.3*df['matched_ndvi'].fillna(df['satellite_ndvi'])+0.2*df['canopy_occupancy_fraction']).round(4)
df.to_csv('scratch/cane_lab_rainfall_canopy_samples.csv',index=False)
base=['Cane Type','Variety Name','crop_age_days','matched_ndvi','matched_ndre','matched_ndwi','matched_lswi','matched_evi','canopy_occupancy_fraction','clear_sky_coverage_pct']
aug=base+['rain_7d','rain_14d','rain_30d','rain_60d','rain_events_30d','dry_days_14d','canopy_growth_proxy']; cat=['Cane Type','Variety Name']; cv=KFold(5,shuffle=True,random_state=42)
for name,features in [('base',base),('rainfall_canopy',aug)]:
    pre=ColumnTransformer([('cat',OneHotEncoder(handle_unknown='ignore'),cat),('num',SimpleImputer(strategy='median'),[x for x in features if x not in cat])])
    for target in ['lab_brix','lab_pol','lab_ccs']:
        model=Pipeline([('preprocess',pre),('regressor',RandomForestRegressor(n_estimators=400,min_samples_leaf=3,max_features=0.8,random_state=42,n_jobs=1))]); p=cross_val_predict(model,df[features],df[target],cv=cv); e=p-df[target]
        print(f'{name} {target}: R2={r2_score(df[target],p):.3f}, MAE={mean_absolute_error(df[target],p):.3f}, RMSE={mean_squared_error(df[target],p)**.5:.3f}, bias={e.mean():+.3f}, MAPE={np.mean(np.abs(e/df[target]))*100:.1f}%')
