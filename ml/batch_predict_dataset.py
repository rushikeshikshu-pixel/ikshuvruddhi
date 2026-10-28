"""Canonical batch prediction: audited source matrix only; no simulated fallback."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
from ml.traceable_quality_engine import predict_frame

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--features',type=Path,default=ROOT/'outputs/real_inputs_rebuild/current_traceable_feature_matrix.csv')
    parser.add_argument('--manifest',type=Path,default=ROOT/'outputs/real_inputs_rebuild/feature_matrix_manifest.json')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/real_inputs_rebuild/traceable_batch_predictions.csv')
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text())
    if manifest.get('schema')!='traceable-inputs-v1' or hashlib.sha256(args.features.read_bytes()).hexdigest()!=manifest['matrix_sha256']:
        raise SystemExit('Unverified input matrix. Run the source-ingestion workflow; synthetic or edited matrices are refused.')
    frame=pd.read_csv(args.features,low_memory=False)
    if len(frame)!=manifest['row_count'] or not frame['Plot No'].is_unique:raise SystemExit('Source row count or plot identity check failed')
    result=predict_frame(frame)
    result.insert(0,'Plot No',frame['Plot No'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    result.to_csv(args.output,index=False,encoding='utf-8-sig')
    print(json.dumps({'rows':len(result),'statuses':result.prediction_refresh_status.value_counts().to_dict(),'output':str(args.output)}))

if __name__=='__main__':main()
