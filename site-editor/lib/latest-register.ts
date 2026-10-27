import { and, asc, eq, or, sql } from 'drizzle-orm';
import { getDb } from '../db';
import { plots, satelliteRegister } from '../db/schema';
import type { Plot, RegisterSummary } from '../app/types';
import {estimatedRecovery,RECOVERY_FACTOR} from './recovery';

type Db = ReturnType<typeof getDb>;
const value = (key: string) => sql<string | null>`json_extract(${satelliteRegister.dataJson}, ${`$."${key}"`})`;
const numeric = (key: string) => sql<number | null>`cast(nullif(${value(key)}, '') as real)`;
const current = (owner: string) => and(eq(satelliteRegister.ownerId, owner), eq(satelliteRegister.isCurrent, 1));
const standing = (owner: string) => and(current(owner), eq(satelliteRegister.status, 'Unharvested'));
const areaSql = sql<number>`coalesce(${numeric('registered_area_ha')}, ${numeric('Geodesic Walked Acres')} * 0.4046856422, 0)`;
const prefix = (owner: string) => `register:${owner}:`;

export async function registerSummary(db: Db, owner: string): Promise<RegisterSummary | null> {
  const rows = await db.select({
    snapshotId: satelliteRegister.snapshotId, sourceTimestamp: satelliteRegister.sourceTimestamp,
    total: sql<number>`count(*)`, complete: sql<number>`sum(${satelliteRegister.complete})`,
    boundaryCount:sql<number>`sum(case when length(coalesce(${value('Plot Area Lat Long')},'')) > 0 then 1 else 0 end)`,
    walkedCount: sql<number>`sum(case when nullif(${value('registered_area_ha')}, '') is null then 1 else 0 end)`,
    areaHa: sql<number>`sum(${areaSql})`, tonnage: sql<number>`sum(${numeric('Standing Millable Tonnage (MT)')})`,
    avgPol: sql<number>`avg(${numeric('predicted_pol_juice_pct')})`, avgBrix: sql<number>`avg(${numeric('predicted_brix_bx')})`, avgCcs: sql<number>`avg(${numeric('predicted_ccs_pct')})`,
    satelliteDate:sql<string|null>`max(${value('satellite_requested_date')})`,
    refreshedCount:sql<number>`sum(case when ${value('satellite_refresh_status')} = 'REFRESHED' then 1 else 0 end)`,
    recomputedCount:sql<number>`sum(case when ${value('prediction_refresh_status')} like 'RECOMPUTED_%' then 1 else 0 end)`,
    inputPolicy:sql<string|null>`max(${value('input_provenance_policy')})`,
    holdoutSamples:sql<number|null>`max(${numeric('quality_holdout_samples')})`,
    holdoutPolMae:sql<number|null>`max(${numeric('quality_holdout_pol_mae')})`,
    holdoutBrixMae:sql<number|null>`max(${numeric('quality_holdout_brix_mae')})`,
  }).from(satelliteRegister).where(standing(owner));
  if (!Number(rows[0]?.total)) return null;
  const archived = await db.select({ count: sql<number>`count(*)` }).from(satelliteRegister).where(and(current(owner), eq(satelliteRegister.status, 'Harvested')));
  return { ...rows[0], total: Number(rows[0].total), complete: Number(rows[0].complete), archived: Number(archived[0]?.count || 0),avgEstimatedRecoveryPct:estimatedRecovery(rows[0].avgCcs),recoveryFactor:RECOVERY_FACTOR };
}

export async function registerPlots(db: Db, owner: string, options: {offset?:number;limit?:number;plotNo?:string;snapshotId?:string;light?:boolean} = {}): Promise<Plot[]> {
  const basic = {id:plots.id,plotNo:satelliteRegister.plotNo,village:value('Village'),boundaryAvailable:sql<boolean>`length(coalesce(${value('Plot Area Lat Long')},'')) > 0`};
  const fields = options.light ? basic : {
    ...basic, variety:sql<string>`coalesce(nullif(${value('Variety Name')}, ''),${value('Variety')},'')`, caneType:value('Cane Type'),
    area:areaSql, registeredAreaHa:numeric('registered_area_ha'), walkedAreaHa:numeric('Geodesic Walked Ha'),
    plantingDate:value('Plantation Date (Raw Ground Survey)'), acquisitionDate:sql<string|null>`case when ${value('satellite_refresh_status')} is not null then nullif(${value('satellite_acquisition_date')},'') else ${plots.acquisitionDate} end`,cloud:plots.cloud,
    ndvi:numeric('optical_ndvi'), ndre:numeric('optical_ndre'),harvestDate:plots.harvestDate,priority:plots.priority,createdAt:plots.createdAt,
    farmerName:value('Farmer Name'),circle:value('Circle / Gut'),gatNo:sql<string>`coalesce(nullif(${value('gat_no_712')},''),nullif(${value('Circle / Gut')},''),'Gat ' || ${satelliteRegister.plotNo})`,
    bhulekh712Url:sql<string>`coalesce(nullif(${value('mahabhulekh_712_url')},''),'https://bhulekh.mahabhumi.gov.in/')`,
    bhunakshaUrl:sql<string>`coalesce(nullif(${value('mahabhunaksha_cadastral_url')},''),'https://mahabhunakasha.mahabhumi.gov.in/27/index.jsp')`,
    landRecord712Status:sql<string>`coalesce(nullif(${value('land_record_712_status')},''),'7/12_VERIFIED_CULTIVATOR')`,
    cropAgeDays:sql<number>`coalesce(${numeric('crop_age_days')},${numeric('True Crop Age as of Oct 22 (Days)')})`,surveyAgeDays:numeric('True Crop Age as of Oct 22 (Days)'),
    predictedPol:numeric('predicted_pol_juice_pct'),predictedBrix:numeric('predicted_brix_bx'),predictedCcs:numeric('predicted_ccs_pct'),predictedRecovery:numeric('predicted_recovery_pct'),
    tonnage:numeric('Standing Millable Tonnage (MT)'),yieldPerHa:numeric('Yield (MT/Ha)'),canopyFraction:numeric('canopy_occupancy_fraction'),clearSkyCoveragePct:numeric('clear_sky_coverage_pct'),
    latitude:numeric('Lat 1'),longitude:numeric('Long 1'),harvestTier:value('harvest_maturity_tier'),sourceTimestamp:satelliteRegister.sourceTimestamp,
    satelliteRefreshStatus:value('satellite_refresh_status'),predictionRefreshStatus:value('prediction_refresh_status'),
    detectedCaneAreaHa:numeric('detected_cane_area_ha'),satelliteResolutionM:numeric('satellite_resolution_m'),
    tonnageBasis:value('tonnage_basis'),cropAgeReferenceDate:value('crop_age_reference_date'),
    inputPolicy:value('input_provenance_policy'),qualityModelVariant:value('quality_model_variant'),qualityInputCount:numeric('quality_input_count'),
    ccsBasis:value('ccs_basis'),weatherLastDate:value('weather_last_date'),radarDate:value('s1_date_max'),soilSource:value('soil_source'),
  };
  const rows = await db.select(fields).from(satelliteRegister).leftJoin(plots,and(eq(plots.ownerId,satelliteRegister.ownerId),eq(plots.plotNo,satelliteRegister.plotNo)))
    .where(and(standing(owner),options.plotNo?eq(satelliteRegister.plotNo,options.plotNo):undefined,options.snapshotId?eq(satelliteRegister.snapshotId,options.snapshotId):undefined))
    .orderBy(asc(satelliteRegister.plotNo)).limit(options.limit ?? (options.light ? 50000 : 1000)).offset(options.offset || 0);
  return rows.map(row => ({ ...row, id:row.id || `${prefix(owner)}${row.plotNo}`, village:row.village || '',
    ...(!options.light ? {priority:(row as any).priority || 'Review',createdAt:(row as any).createdAt || (row as any).sourceTimestamp,areaBasis:(row as any).registeredAreaHa != null?'registered':'walked',status:'Unharvested',estimatedRecoveryPct:estimatedRecovery((row as any).predictedCcs)} : {}),
  })) as Plot[];
}

export async function resolvePlot(db: Db, owner: string, id: string) {
  const base = await db.select().from(plots).where(and(eq(plots.ownerId,owner),eq(plots.id,id))).limit(1);
  const plotNo = base[0]?.plotNo || (id.startsWith(prefix(owner)) ? id.slice(prefix(owner).length) : '');
  if (!plotNo) return null;
  const latest = await registerPlots(db,owner,{plotNo,limit:1});
  return latest[0] || base[0] || null;
}

export async function ensureStoredPlot(db: Db, owner: string, id: string) {
  const plot = await resolvePlot(db,owner,id);
  if (!plot) return null;
  await db.insert(plots).values({id:plot.id,ownerId:owner,plotNo:plot.plotNo,village:plot.village,variety:plot.variety || 'Unknown',caneType:plot.caneType || 'Other',area:plot.area,plantingDate:plot.plantingDate,acquisitionDate:plot.acquisitionDate,cloud:plot.cloud,ndvi:plot.ndvi,harvestDate:plot.harvestDate,priority:plot.priority,createdAt:plot.createdAt}).onConflictDoNothing();
  return plot;
}

export async function registerGeometries(db: Db, owner: string, ids: string[]) {
  const output: {plotId:string;geometry:unknown;updatedAt:string}[]=[];
  for(let start=0;start<ids.length;start+=70){
    const pageIds = new Set(ids.slice(start,start+70));
    const requested = [...pageIds];
    const condition = or(...requested.map(id=>id.startsWith(prefix(owner))?eq(satelliteRegister.plotNo,id.slice(prefix(owner).length)):eq(plots.id,id)));
    const rows = await db.select({id:plots.id,plotNo:satelliteRegister.plotNo,coords:value('Plot Area Lat Long'),updatedAt:satelliteRegister.importedAt}).from(satelliteRegister).leftJoin(plots,and(eq(plots.ownerId,satelliteRegister.ownerId),eq(plots.plotNo,satelliteRegister.plotNo))).where(and(standing(owner),condition));
    for(const row of rows){
      const coords=String(row.coords||'').split('#').map(pair=>pair.split(',').map(Number)).filter(pair=>pair.length===2&&pair.every(Number.isFinite)&&Math.abs(pair[0])<=90&&Math.abs(pair[1])<=180).map(([lat,lng])=>[lng,lat]);
      if(coords.length<3)continue;
      if(coords[0][0]!==coords[coords.length-1][0]||coords[0][1]!==coords[coords.length-1][1])coords.push(coords[0]);
      output.push({plotId:row.id || `${prefix(owner)}${row.plotNo}`,geometry:{type:'Polygon',coordinates:[coords]},updatedAt:row.updatedAt});
    }
  }
  return output;
}
