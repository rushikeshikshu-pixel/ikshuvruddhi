import {fromArrayBuffer} from 'geotiff';
import {gridFor,inside,type Polygon} from './geometry';
export type Secrets={CDSE_CLIENT_ID?:string;CDSE_CLIENT_SECRET?:string};
export type Scene={id:string;date:string;datetime:string;sensor:'S2'|'S1';cloud:number|null;orbit:number|null;direction:string|null};
export class SatelliteError extends Error{constructor(message:string,public status=502){super(message)}}
let tokenCache:{token:string;expires:number;client:string}|undefined;
async function accessToken(secrets:Secrets){
 if(!secrets.CDSE_CLIENT_ID||!secrets.CDSE_CLIENT_SECRET)throw new SatelliteError('Satellite account is not configured.',503);
 if(tokenCache&&tokenCache.client===secrets.CDSE_CLIENT_ID&&tokenCache.expires>Date.now()+60000)return tokenCache.token;
 const response=await fetch('https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token',{method:'POST',redirect:'error',signal:AbortSignal.timeout(20000),headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'client_credentials',client_id:secrets.CDSE_CLIENT_ID,client_secret:secrets.CDSE_CLIENT_SECRET})});
 if(!response.ok)throw new SatelliteError('Copernicus sign-in failed. The site administrator must check the satellite account.',503);
 const data:any=await response.json();if(!data.access_token)throw new SatelliteError('Copernicus did not issue a processing token.');
 tokenCache={token:data.access_token,client:secrets.CDSE_CLIENT_ID,expires:Date.now()+Number(data.expires_in||300)*1000};return tokenCache.token;
}
async function provider(path:string,payload:unknown,secrets:Secrets,accept='application/json'){
 const response=await fetch('https://sh.dataspace.copernicus.eu'+path,{method:'POST',redirect:'error',signal:AbortSignal.timeout(60000),headers:{Authorization:'Bearer '+await accessToken(secrets),'Content-Type':'application/json',Accept:accept},body:JSON.stringify(payload)});
 if(!response.ok){if(response.status===401)tokenCache=undefined;throw new SatelliteError(response.status===429?'Copernicus processing quota is busy. Try later.':'Copernicus request failed (HTTP '+response.status+'). Try later.',response.status===429?429:502);}
 return response;
}
export async function catalogue(geometry:Polygon,sensor:'S2'|'S1',secrets:Secrets,date?:string):Promise<Scene[]>{
 const start=date?date+'T00:00:00Z':new Date(Date.now()-30*86400000).toISOString();const end=date?date+'T23:59:59Z':new Date().toISOString();
 const response=await provider('/catalog/v1/search',{collections:[sensor==='S2'?'sentinel-2-l2a':'sentinel-1-grd'],intersects:geometry,datetime:start+'/'+end,limit:100},secrets);
 const data:any=await response.json();
 return (data.features||[]).map((f:any)=>({id:f.id,date:f.properties.datetime.slice(0,10),datetime:f.properties.datetime,sensor,cloud:typeof f.properties['eo:cloud_cover']==='number'?f.properties['eo:cloud_cover']:null,orbit:f.properties['sat:relative_orbit']??null,direction:f.properties['sat:orbit_state']??null})).sort((a:Scene,b:Scene)=>b.datetime.localeCompare(a.datetime));
}
const opticalScript=`//VERSION=3
function setup(){return {input:[{bands:["B02","B03","B04","B05","B08","B11","SCL","dataMask","CLM","CLP"]}],output:{bands:10,sampleType:"FLOAT32"},mosaicking:"TILE"};}
function evaluatePixel(samples){let s=samples.find(x=>x.dataMask===1&&(x.SCL===4||x.SCL===5)&&x.CLM===0&&x.CLP<=51);if(!s)s=samples.find(x=>x.dataMask===1);if(!s)return [0,0,0,0,0,0,0,0,255,255];return [s.B02,s.B03,s.B04,s.B05,s.B08,s.B11,s.SCL,s.dataMask,s.CLM,s.CLP];}
function updateOutputMetadata(scenes,inputMetadata,outputMetadata){outputMetadata.userData={tiles:scenes.tiles};}`;
const radarScript=`//VERSION=3
function setup(){return {input:[{bands:["VV","VH","dataMask","shadowMask","localIncidenceAngle"]}],output:{bands:5,sampleType:"FLOAT32"},mosaicking:"ORBIT"};}
function evaluatePixel(samples){let s=samples.find(x=>x.dataMask===1);if(!s)return [0,0,0,1,0];return [s.VV,s.VH,s.dataMask,s.shadowMask,s.localIncidenceAngle];}
function updateOutputMetadata(scenes,inputMetadata,outputMetadata){outputMetadata.userData={tiles:(scenes.orbits||[]).reduce((a,o)=>a.concat(o.tiles||[]),[])};}`;
function unpackTar(buffer:ArrayBuffer){
 const bytes=new Uint8Array(buffer);const decoder=new TextDecoder();let raster:ArrayBuffer|undefined;let metadata:any;
 for(let offset=0;offset+512<=bytes.length;){const header=bytes.subarray(offset,offset+512);const name=decoder.decode(header.subarray(0,100)).replace(/\0[\s\S]*$/,'');if(!name)break;const size=parseInt(decoder.decode(header.subarray(124,136)).replace(/\0/g,'').trim(),8);if(!Number.isFinite(size)||size<0||offset+512+size>bytes.length)throw new SatelliteError('Invalid satellite raster response.');const content=bytes.slice(offset+512,offset+512+size);if(/\.tiff?$/.test(name))raster=content.buffer;if(/\.json$/.test(name))metadata=JSON.parse(decoder.decode(content));offset+=512+Math.ceil(size/512)*512;}
 if(!raster||!metadata)throw new SatelliteError('Satellite raster or acquisition metadata is missing.');return {raster,metadata};
}
export type OpticalResult={sensor:'S2';date:string;status:string;totalPixels:number;cleanPixels:number;cleanCoverage:number;canopyFraction:number|null;ndvi:number|null;ndre:number|null;ndwi:number|null;lswi:number|null;evi:number|null;bsi:number|null;sourceScenes:{id:string;datetime:string}[];resolution:number;fetchedAt:string;qualityRules:string};
export function opticalSummary(values:ArrayLike<number>,grid:ReturnType<typeof gridFor>,date:string):OpticalResult{
 const count=grid.width*grid.height;const flagged=new Uint8Array(count),excluded=new Uint8Array(count);
 for(let p=0;p<count;p++){const k=p*10;flagged[p]=Number([3,8,9,10].includes(values[k+6])||values[k+8]===1||values[k+9]>51);}
 // Match the training extractor's three iterations of four-connected dilation at 20 m.
 for(let y=0;y<grid.height;y++)for(let x=0;x<grid.width;x++)if(flagged[y*grid.width+x])for(let dy=-3;dy<=3;dy++)for(let dx=-3;dx<=3;dx++)if(Math.abs(dx)+Math.abs(dy)<=3&&y+dy>=0&&y+dy<grid.height&&x+dx>=0&&x+dx<grid.width)excluded[(y+dy)*grid.width+x+dx]=1;
 let total=0,clean=0,canopy=0;const sums={ndvi:0,ndre:0,ndwi:0,lswi:0,evi:0,bsi:0};
 for(let y=0;y<grid.height;y++)for(let x=0;x<grid.width;x++){
  if(!inside(grid.left+(x+.5)*20,grid.top-(y+.5)*20,grid.points))continue;total++;
  const p=y*grid.width+x,k=p*10; if(values[k+7]!==1||![4,5].includes(values[k+6])||values[k+8]!==0||excluded[p])continue;
  const [b2,b3,b4,b5,b8,b11]=Array.from({length:6},(_,i)=>values[k+i]);
  const v={ndvi:(b8-b4)/(b8+b4+1e-7),ndre:(b8-b5)/(b8+b5+1e-7),ndwi:(b3-b8)/(b3+b8+1e-7),lswi:(b8-b11)/(b8+b11+1e-7),evi:2.5*(b8-b4)/(b8+6*b4-7.5*b2+1),bsi:((b11+b4)-(b8+b2))/((b11+b4)+(b8+b2)+1e-7)};
  if(!Object.values(v).every(Number.isFinite))continue;clean++;for(const key of Object.keys(sums) as (keyof typeof sums)[])sums[key]+=v[key];if(v.ndvi>=.55&&v.ndre>=.12&&v.lswi>=.05&&v.ndwi<=.08&&v.bsi<=.10)canopy++;
 }
 const coverage=total?100*clean/total:0;const fraction=clean?canopy/clean:null;
 const status=!total?'Below grid resolution':!clean?'No clean exact-date pixels':clean<3||coverage<80?'Insufficient clean observations':fraction!<.25?'Insufficient cane-like canopy':'Screened optical observation';
 return {sensor:'S2',date,status,totalPixels:total,cleanPixels:clean,cleanCoverage:coverage,canopyFraction:fraction,...Object.fromEntries(Object.entries(sums).map(([k,v])=>[k,clean?v/clean:null])) as typeof sums,sourceScenes:[],resolution:20,fetchedAt:new Date().toISOString(),qualityRules:'SCL 4/5; CLM=0; CLP≤51/255; 60 m cloud/shadow exclusion; ≥80% clean coverage; ≥3 clean pixels; ≥25% cane-like canopy. Residual haze can remain.'};
}
export async function measure(geometry:Polygon,scene:Scene,secrets:Secrets){
 const grid=gridFor(geometry);const radar=scene.sensor==='S1';
 const from=radar?new Date(Date.parse(scene.datetime)-1000).toISOString():scene.date+'T00:00:00Z';const to=radar?new Date(Date.parse(scene.datetime)+1000).toISOString():scene.date+'T23:59:59Z';
 const payload={input:{bounds:{bbox:[grid.left,grid.bottom,grid.right,grid.top],properties:{crs:'http://www.opengis.net/def/crs/EPSG/0/'+grid.epsg}},data:[{type:radar?'sentinel-1-grd':'sentinel-2-l2a',dataFilter:{timeRange:{from,to},mosaickingOrder:radar?'mostRecent':'leastCC',...(radar?{acquisitionMode:'IW',polarization:'DV'}:{})},processing:radar?{backCoeff:'GAMMA0_TERRAIN',orthorectify:true,demInstance:'COPERNICUS_30',speckleFilter:{type:'LEE',windowSizeX:5,windowSizeY:5}}:{upsampling:'NEAREST',downsampling:'NEAREST'}}]},output:{width:grid.width,height:grid.height,responses:[{identifier:'default',format:{type:'image/tiff'}},{identifier:'userdata',format:{type:'application/json'}}]},evalscript:radar?radarScript:opticalScript};
 const response=await provider('/process/v1',payload,secrets,'application/tar');
 if(Number(response.headers.get('content-length')||0)>10000000)throw new SatelliteError('Satellite response exceeded the field processing limit.');
 const buffer=await response.arrayBuffer();if(buffer.byteLength>10000000)throw new SatelliteError('Satellite response exceeded the field processing limit.');
 const {raster,metadata}=unpackTar(buffer);const tiles:any[]=metadata.tiles||[];
 if(!tiles.length||tiles.some(t=>typeof t.date!=='string'||t.date.slice(0,10)!==scene.date))throw new SatelliteError('No verified acquisition on the selected day. No estimate saved.',422);
 if(radar&&tiles.some(t=>Math.abs(Date.parse(t.date)-Date.parse(scene.datetime))>60000))throw new SatelliteError('Radar acquisition did not match the selected scene.',422);
 const tiff=await fromArrayBuffer(raster);const image=await tiff.getImage();if(image.getWidth()!==grid.width||image.getHeight()!==grid.height||image.getSamplesPerPixel()!==(radar?5:10))throw new SatelliteError('Unexpected satellite raster grid.');
 const values=await image.readRasters({interleave:true});
 const sourceScenes=tiles.map(t=>({id:String(t.sentinel2ProductId||t.sentinel1ProductId||t.productId||t.shId),datetime:t.date}));
 if(!radar)return {...opticalSummary(values as ArrayLike<number>,grid,scene.date),sourceScenes};
 let total=0,valid=0,vv=0,vh=0,angle=0;
 for(let y=0;y<grid.height;y++)for(let x=0;x<grid.width;x++)if(inside(grid.left+(x+.5)*20,grid.top-(y+.5)*20,grid.points)){total++;const k=(y*grid.width+x)*5;if(values[k+2]===1&&values[k+3]===0&&values[k]>0&&values[k+1]>0&&Number.isFinite(values[k+4])&&values[k+4]>=20&&values[k+4]<=50){valid++;vv+=values[k];vh+=values[k+1];angle+=values[k+4];}}
 return {sensor:'S1' as const,date:scene.date,status:valid>=3&&total&&valid/total>=.8?'Radar observation':'Insufficient valid radar pixels',totalPixels:total,validPixels:valid,validCoverage:total?100*valid/total:0,vvDb:valid?10*Math.log10(vv/valid):null,vhDb:valid?10*Math.log10(vh/valid):null,vhVvRatio:valid?vh/vv:null,incidenceAngle:valid?angle/valid:null,orbit:scene.orbit,direction:scene.direction,sourceScenes,resolution:20,fetchedAt:new Date().toISOString(),qualityRules:'Terrain-corrected gamma0; Lee 5×5 speckle filter; radar-shadow exclusion; incidence 20–50°; ≥80% valid coverage and ≥3 pixels. Cloud-insensitive; moisture, speckle and geometry effects remain. No radar sugar-quality model is calibrated.'};
}
