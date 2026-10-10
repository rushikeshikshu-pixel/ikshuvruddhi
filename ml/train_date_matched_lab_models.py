import pickle, pandas as pd, numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from copernicus_client import CopernicusCDSEProcessEngine

src = pd.read_csv('data/2026-27_cane_plantation_data_enriched_live.csv')
lab=pd.read_csv('scratch/pdf_lab_dates.csv').merge(src,on='Plot No',validate='one_to_one')
lab['sample_date']=pd.to_datetime(lab['sample_date'])
engine=CopernicusCDSEProcessEngine()
metrics=[]; statuses=[]
for i,row in lab.iterrows():
    poly=[[float(p.split(',')[0]),float(p.split(',')[1])] for p in str(row['Plot Area Lat Long']).split('#')]
    result=engine.fetch_real_sentinel2_l2a_raster(poly, row['sample_date'].strftime('%Y-%m-%d'))
    cells=[c for c in result.get('cells',[]) if c.get('scl_valid') and c.get('ndvi') is not None]
    if cells:
        metrics.append({k:float(np.mean([c[k] for c in cells])) for k in ['ndvi','ndre','ndwi','lswi']})
        statuses.append(result.get('status'))
    else:
        metrics.append({k:np.nan for k in ['ndvi','ndre','ndwi','lswi']}); statuses.append(result.get('status','NO_DATA'))
    print(f'{i+1}/{len(lab)} {row["Plot No"]} {statuses[-1]}',flush=True)
for k in ['ndvi','ndre','ndwi','lswi']: lab['matched_'+k]=[m[k] for m in metrics]
lab['matched_evi']=lab['matched_ndvi']*0.82
lab['satellite_status']=statuses
lab.to_csv('scratch/cane_lab_date_matched_samples.csv',index=False)
features=['Cane Type','Variety Name','crop_age_days','matched_ndvi','matched_ndre','matched_ndwi','matched_lswi','matched_evi','canopy_occupancy_fraction','clear_sky_coverage_pct']
cat=['Cane Type','Variety Name']; num=[x for x in features if x not in cat]
pre=ColumnTransformer([('cat',OneHotEncoder(handle_unknown='ignore'),cat),('num',SimpleImputer(strategy='median'),num)])
cv=KFold(n_splits=5,shuffle=True,random_state=42)
for target in ['lab_brix','lab_pol','lab_ccs']:
    model=Pipeline([('preprocess',pre),('regressor',RandomForestRegressor(n_estimators=400,min_samples_leaf=3,max_features=0.8,random_state=42,n_jobs=1))])
    pred=cross_val_predict(model,lab[features],lab[target],cv=cv); e=pred-lab[target]
    print(f'{target}: R2={r2_score(lab[target],pred):.3f}, MAE={mean_absolute_error(lab[target],pred):.3f}, RMSE={mean_squared_error(lab[target],pred)**0.5:.3f}, MAPE={np.mean(np.abs(e/lab[target]))*100:.1f}%')
    model.fit(lab[features],lab[target]); pickle.dump({'pipeline':model,'features':features,'target':target,'training_samples':len(lab),'source':'cane sampale list.pdf; date-matched Sentinel-2'},open(f'models/date_matched_{target[4:]}.pkl','wb'))
print('Saved date-matched models.')
