import { z } from 'zod';
import proj4 from 'proj4';
export type Polygon = {type:'Polygon';coordinates:number[][][]};
const coordinate=z.tuple([z.number().finite().min(-180).max(180),z.number().finite().min(-60).max(84)]);
export function parseBoundary(input:unknown):Polygon {
 const raw=z.object({type:z.literal('Polygon'),coordinates:z.array(z.array(coordinate).min(4).max(201)).length(1)}).parse(input);
 const ring=raw.coordinates[0]; const last=ring[ring.length-1];
 if(ring[0][0]!==last[0]||ring[0][1]!==last[1])throw Error('Close the polygon ring by repeating the first coordinate.');
 if(new Set(ring.slice(0,-1).map(p=>p.join(','))).size!==ring.length-1)throw Error('Boundary contains repeated vertices.');
 function cross(a:number[],b:number[],c:number[]){return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])}
 function between(a:number[],b:number[],p:number[]){return Math.abs(cross(a,b,p))<1e-12&&p[0]>=Math.min(a[0],b[0])&&p[0]<=Math.max(a[0],b[0])&&p[1]>=Math.min(a[1],b[1])&&p[1]<=Math.max(a[1],b[1])}
 for(let i=0;i<ring.length-1;i++)for(let j=i+2;j<ring.length-1;j++){
  if(i===0&&j===ring.length-2)continue;const [a,b,c,d]=[ring[i],ring[i+1],ring[j],ring[j+1]];
  if((cross(a,b,c)*cross(a,b,d)<0&&cross(c,d,a)*cross(c,d,b)<0)||between(a,b,c)||between(a,b,d)||between(c,d,a)||between(c,d,b))throw Error('Boundary crosses or touches itself.');
 }
 const area=Math.abs(ring.slice(0,-1).reduce((s,a,i)=>s+a[0]*ring[i+1][1]-ring[i+1][0]*a[1],0));
 if(area<1e-12)throw Error('Boundary has no usable area.');
 gridFor(raw);return raw;
}
export function gridFor(geometry:Polygon){
 const ring=geometry.coordinates[0];const lon=ring.reduce((s,p)=>s+p[0],0)/ring.length;const lat=ring.reduce((s,p)=>s+p[1],0)/ring.length;
 const zone=Math.floor((lon+180)/6)+1;const epsg=(lat<0?32700:32600)+zone;
 const projection=`+proj=utm +zone=${zone} ${lat<0?'+south ':''}+datum=WGS84 +units=m +no_defs`;
 const points=ring.map(p=>proj4('EPSG:4326',projection,p));
 const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
 const left=Math.floor(Math.min(...xs)/20)*20-80,top=Math.ceil(Math.max(...ys)/20)*20+80;
 const right=Math.ceil(Math.max(...xs)/20)*20+80,bottom=Math.floor(Math.min(...ys)/20)*20-80;
 const width=(right-left)/20,height=(top-bottom)/20;
 if(width>128||height>128||Math.max(...ring.map(p=>p[0]))-Math.min(...ring.map(p=>p[0]))>1)throw Error('Boundary is too large. Use one field spanning at most 2.4 km per side.');
 return {points,epsg,left,top,right,bottom,width,height,resolution:20};
}
export function inside(x:number,y:number,ring:number[][]){let yes=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>y)!==(b[1]>y)&&x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])yes=!yes;}return yes;}
export async function boundaryHash(geometry:Polygon){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(geometry))))).map(x=>x.toString(16).padStart(2,'0')).join('');}
