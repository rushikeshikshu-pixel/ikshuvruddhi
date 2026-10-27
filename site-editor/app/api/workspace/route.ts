import { getMillUser } from "../../session-auth";
import { getDb } from "../../../db";
import { mills, plots, samples, boundaries, satelliteObservations, satelliteRequests, satelliteRegister } from "../../../db/schema";
import { and, eq, desc, sql } from "drizzle-orm";
import { z } from "zod";
import { registerPlots, registerSummary, ensureStoredPlot } from "../../../lib/latest-register";
export const dynamic = "force-dynamic";
import {plotInput,sampleInput,label,date,optionalDate} from "../../validation";
function json(data:unknown,status=200){return Response.json(data,{status,headers:{'Cache-Control':'private, no-store'}})}
export async function GET(request:Request){
 const user=await getMillUser();if(!user)return json({error:'Sign in to access mill records'},401);
 try{
  const db=getDb();const params=new URL(request.url).searchParams;const owner=user.userId;
  const active=await db.select({snapshotId:satelliteRegister.snapshotId,sourceTimestamp:satelliteRegister.sourceTimestamp}).from(satelliteRegister).where(and(eq(satelliteRegister.ownerId,owner),eq(satelliteRegister.isCurrent,1),eq(satelliteRegister.status,'Unharvested'))).limit(1);
  if(params.get('snapshotId')&&params.get('snapshotId')!==active[0]?.snapshotId)return json({error:'The active register changed. Reload the dashboard.'},409);
  if(params.get('view')==='version')return json({snapshotId:active[0]?.snapshotId||null,sourceTimestamp:active[0]?.sourceTimestamp||null});
  if(params.get('view')==='satellite'){
   const p=active.length?await registerPlots(db,owner,{light:true}):await db.select({id:plots.id,plotNo:plots.plotNo,village:plots.village}).from(plots).where(eq(plots.ownerId,owner));
   return json({plots:p,sourceSnapshotId:active[0]?.snapshotId||null});
  }
  const offset=Math.max(0,Number(params.get('offset')||0));const limit=Math.min(1000,Math.max(1,Number(params.get('limit')||1000)));
  const [m,p,s,register,totalRows]=await Promise.all([
   db.select().from(mills).where(eq(mills.ownerId,owner)),
   active.length?registerPlots(db,owner,{offset,limit}):db.select().from(plots).where(eq(plots.ownerId,owner)).orderBy(desc(plots.createdAt)).limit(limit).offset(offset),
   offset?Promise.resolve([]):db.select().from(samples).where(eq(samples.ownerId,owner)).orderBy(desc(samples.sampleDate)),
   active.length&&!offset?registerSummary(db,owner):Promise.resolve(null),
   active.length?db.select({count:sql<number>`count(*)`}).from(satelliteRegister).where(and(eq(satelliteRegister.ownerId,owner),eq(satelliteRegister.isCurrent,1),eq(satelliteRegister.status,'Unharvested'))):db.select({count:sql<number>`count(*)`}).from(plots).where(eq(plots.ownerId,owner)),
  ]);
  const total=Number(totalRows[0]?.count||0);const fallback=owner==='mill_gangamai_sugar'?{name:'Gangamai Industries and Commerce Ltd.',location:'Shevgaon, Ahmednagar, Maharashtra',season:'2026–27'}:null;
  return json({mill:m[0]?{name:m[0].name,location:m[0].location,season:m[0].season}:fallback,plots:p.map(({ownerId,...r}:any)=>r),samples:s.map(({ownerId,...r})=>r),register,pagination:{offset,limit,total,hasMore:offset+p.length<total,snapshotId:active[0]?.snapshotId||null}});
 }catch{return json({error:'Workspace storage is temporarily unavailable. Please retry.'},503)}
}
export async function POST(request:Request){const user=await getMillUser();if(!user)return json({error:'Sign in required'},401);const origin=request.headers.get('origin');if(!origin||origin!==new URL(request.url).origin)return json({error:'Invalid request origin'},403);if(Number(request.headers.get('content-length')||0)>3000000)return json({error:'Import too large'},413);try{const raw=await request.text();if(raw.length>3000000)return json({error:'Import too large'},413);const body=JSON.parse(raw);const db=getDb();const ownerId=user.userId;const now=new Date().toISOString();
  if(body.action==='mill'){const v=z.object({name:label,location:label,season:z.string().trim().min(1).max(30)}).parse(body.data);await db.insert(mills).values({ownerId,...v}).onConflictDoUpdate({target:mills.ownerId,set:v});return json({ok:true})}
  const m=await db.select().from(mills).where(eq(mills.ownerId,ownerId));if(!m.length&&ownerId==='mill_gangamai_sugar'){await db.insert(mills).values({ownerId,name:'Gangamai Industries and Commerce Ltd.',location:'Shevgaon, Ahmednagar, Maharashtra',season:'2026–27'}).onConflictDoNothing()}else if(!m.length)return json({error:'Set up your mill first'},409);
  if(body.action==='plot'){const v=plotInput.parse(body.data);const existing=await db.select({id:plots.id}).from(plots).where(and(eq(plots.ownerId,ownerId),eq(plots.plotNo,v.plotNo)));if(existing.length)return json({error:'Plot number already exists'},409);await db.insert(plots).values({id:crypto.randomUUID(),ownerId,...v,createdAt:now});return json({ok:true})}
  if(body.action==='import'){const rows=z.array(plotInput).min(1).max(500).parse(body.data);if(new Set(rows.map(x=>x.plotNo)).size!==rows.length)return json({error:'Duplicate plot numbers in import'},400);const exists=await db.select({plotNo:plots.plotNo}).from(plots).where(eq(plots.ownerId,ownerId));const ids=new Set(exists.map(x=>x.plotNo));const duplicate=rows.find(x=>ids.has(x.plotNo));if(duplicate)return json({error:'Plot '+duplicate.plotNo+' already exists. Import only new plots.'},409);const operations=rows.map(v=>db.insert(plots).values({id:crypto.randomUUID(),ownerId,...v,createdAt:now}));await db.batch(operations as [typeof operations[number],...typeof operations[number][]]);return json({ok:true,count:rows.length})}
  if(body.action==='sample'){const v=sampleInput.parse(body.data);const p=await ensureStoredPlot(db,ownerId,v.plotId);if(!p)return json({error:'Plot not found'},404);if(v.sampleDate<p.plantingDate)return json({error:'Sample date must follow planting'},400);await db.insert(samples).values({id:crypto.randomUUID(),ownerId,...v,createdAt:now});return json({ok:true})}
  if(body.action==='plan'){const v=z.object({id:label,harvestDate:optionalDate,priority:z.enum(['Review','Ready','Hold'])}).parse(body.data);const p=await ensureStoredPlot(db,ownerId,v.id);if(!p)return json({error:'Plot not found'},404);if(v.harvestDate&&v.harvestDate<p.plantingDate)return json({error:'Harvest must follow planting'},400);await db.update(plots).set({harvestDate:v.harvestDate??null,priority:v.priority}).where(and(eq(plots.id,v.id),eq(plots.ownerId,ownerId)));return json({ok:true})}
  if(body.action==='observation'){const v=z.object({id:label,acquisitionDate:date,cloud:z.number().min(0).max(100),ndvi:z.number().min(-1).max(1)}).parse(body.data);const p=await ensureStoredPlot(db,ownerId,v.id);if(!p)return json({error:'Plot not found'},404);if(v.acquisitionDate<p.plantingDate)return json({error:'Acquisition must follow planting'},400);await db.update(plots).set({acquisitionDate:v.acquisitionDate,cloud:v.cloud,ndvi:v.ndvi}).where(and(eq(plots.id,v.id),eq(plots.ownerId,ownerId)));return json({ok:true})}
  if(body.action==='deletePlot'){const id=label.parse(body.id);await db.batch([db.delete(samples).where(and(eq(samples.plotId,id),eq(samples.ownerId,ownerId))),db.delete(satelliteObservations).where(and(eq(satelliteObservations.plotId,id),eq(satelliteObservations.ownerId,ownerId))),db.delete(boundaries).where(and(eq(boundaries.plotId,id),eq(boundaries.ownerId,ownerId))),db.delete(plots).where(and(eq(plots.id,id),eq(plots.ownerId,ownerId)))]);return json({ok:true})}
  if(body.action==='deleteSample'){await db.delete(samples).where(and(eq(samples.id,label.parse(body.id)),eq(samples.ownerId,ownerId)));return json({ok:true})}
  if(body.action==='erase'){if(body.confirmation!=='ERASE')return json({error:'Confirmation required'},400);await db.batch([db.delete(samples).where(eq(samples.ownerId,ownerId)),db.delete(satelliteObservations).where(eq(satelliteObservations.ownerId,ownerId)),db.delete(boundaries).where(eq(boundaries.ownerId,ownerId)),db.delete(satelliteRequests).where(eq(satelliteRequests.ownerId,ownerId)),db.delete(plots).where(eq(plots.ownerId,ownerId)),db.delete(satelliteRegister).where(eq(satelliteRegister.ownerId,ownerId)),db.delete(mills).where(eq(mills.ownerId,ownerId))]);return json({ok:true})}
  return json({error:'Unknown action'},400);
}catch(e){if(e instanceof z.ZodError)return json({error:e.issues[0]?.message||'Invalid input'},400);if(e instanceof SyntaxError)return json({error:'Invalid request'},400);if(String(e).includes('UNIQUE'))return json({error:'Plot number already exists'},409);return json({error:'Unable to save. Please retry; your records have not been confirmed saved.'},503)}}

