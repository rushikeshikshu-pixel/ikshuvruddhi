"""Export the existing audited 161-sample model, with no private lab rows."""
from pathlib import Path
import json, hashlib, pickle
import numpy as np
import pandas as pd

root=Path(r'C:\Users\rishi\.gemini\antigravity\SatCane-AI-Engine')
workspace=Path('../..')
audit=json.loads((workspace/'outputs/accuracy_goal_audit/independent_model_accuracy_audit.json').read_text())
blob=(root/'models/sota_retrained_oct2026.pkl').read_bytes()
assert hashlib.sha256(blob).hexdigest()==audit['model_sha256'], 'Model changed since independent audit'
training=(root/'data/combined_161_clean_32param_lab_samples.csv').read_bytes()
assert hashlib.sha256(training).hexdigest()==audit['training_data_sha256']
bundle=pickle.loads(blob)
features=bundle['features']
frame=pd.read_csv(root/'data/combined_161_clean_32param_lab_samples.csv')
assert len(frame)==161 and features==audit['features']
outputs={}
for target,model in bundle['models'].items():
    trees=[]
    for estimator in model.estimators_:
        t=estimator.tree_
        trees.append(dict(left=t.children_left.tolist(),right=t.children_right.tolist(),feature=t.feature.tolist(),threshold=t.threshold.tolist(),value=t.value[:,0,0].tolist()))
    expected=model.predict(frame[features])
    actual=[]
    for vector in frame[features].to_numpy(dtype=np.float32):
        values=[]
        for tree in trees:
            node=0
            while tree['left'][node]!=-1:
                node=tree['left'][node] if float(vector[tree['feature'][node]])<=tree['threshold'][node] else tree['right'][node]
            values.append(tree['value'][node])
        actual.append(float(np.mean(values)))
    assert np.max(np.abs(expected-actual))<1e-10, (target, float(np.max(np.abs(expected-actual))))
    outputs[target]=trees
artifact={'features':features,'outputs':outputs,'sourceModelSha256':audit['model_sha256']}
raw=json.dumps(artifact,separators=(',',':'),allow_nan=False)
target_names={'target_pol_juice':'Pol in juice','target_brix':'Brix','target_pol_cane':'Pol in cane','target_recovery':'Mill recovery'}
metrics={}
for target,name in target_names.items():
    group=next(r for r in audit['validation_results'] if r['target']==target and r['validation']=='village_heldout')
    temporal=next(r for r in audit['validation_results'] if r['target']==target and r['validation']=='September_train_October_test')
    metrics[name]={'model':{k:group[k] for k in ['MAE','RMSE','R2']},'mean_baseline':{'MAE':group['baseline_MAE']},'withinOnePointPct':group['within_1_0_pct'],'laterDate':{k:temporal[k] for k in ['MAE','RMSE','R2']},'laterDateWithinOnePointPct':temporal['within_1_0_pct']}
meta={'version':'retrained-161-oct2026-'+audit['model_sha256'][:12],'status':'Research model: later-date validation remains weak','sourceModelSha256':audit['model_sha256'],'artifactSha256':hashlib.sha256(raw.encode()).hexdigest(),'features':features,'featureCount':len(features),'trainingSamples':161,'trainingGroups':audit['village_groups'],'validation':'5-fold village holdout on 161 lab-labelled records','laterDateValidation':'Train on 78 September samples; test on 83 October samples','metrics':metrics,'qualityPredictionsEnabled':False,'predictionNote':'The 161-sample model requires all 27 dated satellite, weather, soil and crop inputs. A single satellite scene cannot supply them. Later-date held-out R² is negative for every saved target, so operational quality estimates remain withheld.','ccsDefinition':'Mill recovery is a separate training target, not standard CCS. CCS derived from juice Pol and Brix requires its own validation.','parityRows':161,'parityTolerance':1e-10}
Path('lib/satellite/retrained-forest.json').write_text(raw)
Path('lib/satellite/retrained-model-info.json').write_text(json.dumps(meta,indent=2))
print(json.dumps({'version':meta['version'],'features':len(features),'samples':161,'targets':len(outputs),'parityRows':161,'artifactBytes':len(raw),'privateRowsExported':False}))
