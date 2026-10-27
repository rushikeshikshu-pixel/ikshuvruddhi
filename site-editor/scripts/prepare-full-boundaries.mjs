import { readFileSync, writeFileSync } from 'node:fs';
import { parseBoundary } from '../lib/satellite/geometry.ts';
const root = '../../outputs/ikshu-website/full-register/';
const source = JSON.parse(readFileSync(root+'boundary-candidates.geojson','utf8'));
const features = [], rejected = [];
for (const feature of source.features) {
  try { parseBoundary(feature.geometry); features.push(feature); }
  catch (error) { rejected.push({plotNo:feature.properties.plotNo,reason:error.message}); }
}
const raw=JSON.stringify({type:'FeatureCollection',features});
writeFileSync(root+'all-valid-plot-boundaries.geojson',raw);
writeFileSync(root+'boundary-exceptions.json',JSON.stringify(rejected,null,2));
console.log(JSON.stringify({source:source.features.length,valid:features.length,rejected:rejected.length,bytes:raw.length}));
