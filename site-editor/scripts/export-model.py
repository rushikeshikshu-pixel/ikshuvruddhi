"""Export only learned tree parameters and aggregate model metadata, never farmer rows."""
import json, pickle, hashlib
from pathlib import Path
import numpy as np
source=Path('../../outputs/cane_20261007')
bundle=pickle.load(open(source/'clean_optical_exploratory_model.pkl','rb'))
model=bundle['model']; metadata=bundle['metadata']
features=bundle['features']; numeric=features[:-2]
categories=[list(x) for x in model.named_steps['pre'].named_transformers_['cat'].categories_]
trees=[]
for estimator in model.named_steps['rf'].estimators_:
 t=estimator.tree_
 trees.append({'left':t.children_left.tolist(),'right':t.children_right.tolist(),'feature':t.feature.tolist(),'threshold':t.threshold.tolist(),'value':t.value[:,:,0].tolist()})
artifact={'numeric':numeric,'categories':categories,'trees':trees}
raw=json.dumps(artifact,separators=(',',':'),allow_nan=False)
version='optical-20261005-'+hashlib.sha256(raw.encode()).hexdigest()[:12]
rows=json.loads((source/'calibration_records.json').read_text())
ranges={key:[min(r[key] for r in rows),max(r[key] for r in rows)] for key in numeric if key!='crop_age_days'}
public={'version':version,'status':'Exploratory: weak held-out skill','features':features,'trainingSamples':metadata['clean_training_samples'],'trainingGroups':metadata['training_groups'],'validation':metadata['validation'],'metrics':metadata['metrics'],'supportedVarieties':metadata['supported_varieties'],'supportedTypes':metadata['supported_types'],'supportedAgeDays':[metadata['supported_age_days'][0]-5,metadata['supported_age_days'][1]+5],'featureRanges':ranges,'sampleDateAssumption':metadata['lab_date_assumption'],'ccsDefinition':metadata['CCS_definition']}
Path('lib/satellite').mkdir(parents=True,exist_ok=True)
Path('lib/satellite/forest.json').write_text(raw)
Path('lib/satellite/model-info.json').write_text(json.dumps(public,indent=2))
# Independently traverse exported trees and compare sklearn output on all calibration rows.
for row in rows:
 x=[row[k] for k in numeric]+[float(row[k]==category) for k,cats in zip(features[-2:],categories) for category in cats]
 values=[]
 for tree in trees:
  node=0
  while tree['left'][node]!=-1:
   node=tree['left'][node] if np.float32(x[tree['feature'][node]])<=tree['threshold'][node] else tree['right'][node]
  values.append(tree['value'][node])
 import pandas as pd
 actual=model.predict(pd.DataFrame([{k:row[k] for k in features}]))[0]
 assert np.max(np.abs(np.mean(values,axis=0)-actual))<1e-10
print(json.dumps({'version':version,'trees':len(trees),'parityRows':len(rows),'maxTolerance':1e-10,'privateRowsExported':False}))
