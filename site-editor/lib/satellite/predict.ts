import info from './retrained-model-info.json';
import type { OpticalResult } from './process';
export function predictQuality(observation:OpticalResult,plot:{plantingDate:string;variety:string;caneType:string},_geometry:{coordinates:number[][][]}){
 const cropAgeDays=Math.round((Date.parse(observation.date)-Date.parse(plot.plantingDate))/86400000);
 return {status:'Withheld',reason:info.predictionNote,modelVersion:info.version,pol:null,brix:null,ccs:null,cropAgeDays,requiredFeatureCount:info.featureCount};
}
