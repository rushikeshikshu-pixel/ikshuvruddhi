import pickle
import pandas as pd

src = pd.read_csv('data/2026-27_cane_plantation_data_enriched_live.csv')
src['plant_dt'] = pd.to_datetime(src['Plantation Date'], errors='coerce')
src['plant_month'] = src['plant_dt'].dt.month
features = ['Cane Type','Variety Name','crop_age_days','matched_ndvi','matched_ndre','matched_ndwi','matched_lswi','matched_evi','canopy_occupancy_fraction','clear_sky_coverage_pct']
# Use the date-matched sample medians for satellite fields when applying to the full register.
matched = pd.read_csv('scratch/cane_lab_date_matched_samples.csv')
for k in ['ndvi','ndre','ndwi','lswi']:
    src['matched_'+k] = src['satellite_'+k].fillna(matched['matched_'+k].median())
src['matched_evi'] = src['matched_ndvi'] * 0.82
for target, out_col in [('brix','predicted_brix_bx'),('pol','predicted_pol_pct'),('ccs','predicted_ccs_pct')]:
    model = pickle.load(open(f'models/date_matched_{target}.pkl','rb'))['pipeline']
    src[out_col] = model.predict(src[features]).round(2)
src['predicted_purity_pct'] = (src['predicted_pol_pct'] / src['predicted_brix_bx'] * 100).round(1)
# Operational tonnage basis: satellite-detected cane area, not full registered/boundary area.
src['predicted_tonnage_mt'] = (src['detected_cane_ha'] * src['yield_tonnes_per_ha']).round(1)
area_ratio = (src['geodesic_area_ha'] / src['registered_area_ha']).replace([float('inf'), -float('inf')], pd.NA)
src['area_evidence_status'] = 'Satellite-supported estimate'
src.loc[src['geodesic_area_ha'].notna() & area_ratio.between(0.5, 2.0), 'area_evidence_status'] = 'Gat/polygon-supported'
src.loc[src['geodesic_area_ha'].notna() & ~area_ratio.between(0.5, 2.0), 'area_evidence_status'] = 'Field audit required'
result = src[['Plot No','Gut','Farmer','Village','Cane Type','Variety Name','Plantation Date','Area (Hectare','detected_cane_ha','area_evidence_status','predicted_pol_pct','predicted_brix_bx','predicted_ccs_pct','predicted_tonnage_mt']].copy()
result.columns = ['Plot No','Gut No','Farmer','Village','Cane Type','Variety Name','Plantation Date','Registered Area (Hectare)','Detected Cane Area (Hectare)','Area Evidence Status','Predicted Pol (%)','Predicted Brix (°Bx)','Predicted CCS (%)','Predicted Tonnage (MT)']
result.to_csv('data/sugar_mill_predictions_retrained.csv', index=False)
print('rows',len(result)); print(result[['Registered Area (Hectare)','Detected Cane Area (Hectare)','Predicted Pol (%)','Predicted Brix (°Bx)','Predicted CCS (%)','Predicted Tonnage (MT)']].mean().round(2).to_string())
print('saved data/sugar_mill_predictions_retrained.csv')
