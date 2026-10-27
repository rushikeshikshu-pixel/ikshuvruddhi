import { and, asc, eq, like, sql } from 'drizzle-orm';
import { z } from 'zod';
import { getDb } from '../../../db';
import { mills, plots, satelliteRegister } from '../../../db/schema';
import { getMillUser } from '../../session-auth';
import {estimatedRecovery,recoveryForExport,RECOVERY_FACTOR} from '../../../lib/recovery';

export const dynamic = 'force-dynamic';
const json = (data: unknown, status = 200) => Response.json(data, { status, headers: { 'Cache-Control': 'private, no-store' } });

export async function GET(request: Request) {
  const user = await getMillUser();
  if (!user) return json({ error: 'Sign in to access mill records' }, 401);
  try {
    const db = getDb();
    const params = new URL(request.url).searchParams;
    const offset = Math.max(0, Number(params.get('offset') || 0));
    const limit = Math.min(100, Math.max(1, Number(params.get('limit') || 50)));
    const query = (params.get('q') || '').trim().slice(0, 80);
    const statusFilter = params.get('status');
    const current = and(eq(satelliteRegister.ownerId, user.userId), eq(satelliteRegister.isCurrent, 1));
    const where = and(current,
      query ? like(satelliteRegister.plotNo, `%${query}%`) : undefined,
      statusFilter === 'Unharvested' || statusFilter === 'Harvested' ? eq(satelliteRegister.status, statusFilter) : undefined,
    );
    if (params.get('format') === 'csv') {
      const exportCountRows = await db.select({ total: sql<number>`count(*)` }).from(satelliteRegister).where(where);
      const exportTotal = Number(exportCountRows[0]?.total || 0);
      const marathi=params.get('lang')==='mr';
      const columns = ['Plot No', 'Farmer', 'Village', 'Plantation Date', 'Cane Type', 'Variety', 'Area (ha)', 'Area Basis', 'Crop Age (days)', 'Crop Age Basis', 'Predicted Pol (%)', 'Predicted Brix (°Bx)', 'Predicted CCS (%)', 'Estimated recovery (%)', 'Standing Millable Tonnage (MT)', 'Register Status','Source calculation timestamp','Survey crop age (22 Oct 2026)','Recovery factor','Sentinel-2 acquisition date','Satellite refresh status','Prediction refresh status','NDVI','NDRE','Clear-sky coverage (%)','Satellite-supported candidate cane area (ha)','Tonnage basis','Input source policy','Quality model','Model input count','CCS basis','Weather through','Sentinel-1 date','Validation status'];
      const marathiColumns=['प्लॉट क्रमांक','शेतकरी','गाव','लागवड तारीख','ऊस प्रकार','वाण','क्षेत्र (हे.)','क्षेत्राचा आधार','पीक वय (दिवस)','पीक वयाचा आधार','अंदाजित पोल (%)','अंदाजित ब्रिक्स (°Bx)','अंदाजित CCS (%)','अंदाजित साखर उतारा (%)','उभ्या उसाचे वजन (MT)','नोंदवही स्थिती','मूळ गणना वेळ','सर्वेक्षणातील वय (२२ ऑक्टोबर २०२६)','उतारा गुणांक','सेंटिनेल-२ प्रतिमा तारीख','उपग्रह अद्ययावत स्थिती','अंदाज अद्ययावत स्थिती','NDVI','NDRE','स्वच्छ आकाश व्याप्ती (%)','उपग्रहाधारित संभाव्य ऊस क्षेत्र (हे.)','वजन गणनेचा आधार','माहिती स्रोत धोरण','गुणवत्ता मॉडेल','मॉडेल घटक संख्या','CCS गणनेचा आधार','हवामान उपलब्ध तारीख','सेंटिनेल-१ तारीख','पडताळणी स्थिती'];
      const quote = (value: unknown) => `"${String(value ?? '').replaceAll('"', '""')}"`;
      const encoder = new TextEncoder();
      const stream = new ReadableStream<Uint8Array>({
        async start(controller) {
          try {
            controller.enqueue(encoder.encode(`\uFEFF${(marathi?marathiColumns:columns).map(quote).join(',')}\r\n`));
            let cursor = 0;
            while (cursor < exportTotal) {
              const batch = await db.select({ plotNo: satelliteRegister.plotNo, status: satelliteRegister.status, sourceTimestamp:satelliteRegister.sourceTimestamp,dataJson: satelliteRegister.dataJson })
                .from(satelliteRegister).where(where).orderBy(asc(satelliteRegister.plotNo)).limit(500).offset(cursor);
              if (!batch.length) break;
              const lines = batch.map(row => {
                const data = JSON.parse(row.dataJson) as Record<string, unknown>;
                const registered = String(data.registered_area_ha ?? '').trim();
                const walkedAcres = Number(String(data['Geodesic Walked Acres'] ?? '').trim());
                const areaHa = registered ? registered : Number.isFinite(walkedAcres) && walkedAcres > 0 ? (walkedAcres * 0.4046856422).toFixed(4) : '';
                const age = String(data.crop_age_days ?? '').trim() || String(data['True Crop Age as of Oct 22 (Days)'] ?? '').trim();
                const crop=String(data['Cane Type']||data.caneType||'');
                const cropMr:Record<string,string>={Suru:'सुरू',Khodwa:'खोडवा',Adsali:'आडसाली','Purva Hungami':'पूर्वहंगामी'};
                const values = [row.plotNo,data['Farmer Name'],data.Village||data.village,data['Plantation Date (Raw Ground Survey)']||data.planting_date,marathi?cropMr[crop]||crop:crop,data['Variety Name']||data.Variety||data.variety,areaHa,registered?(marathi?'नोंदणीकृत क्षेत्र':'Registered area'):areaHa?(marathi?'GPS मोजणीचे एकर हेक्टरमध्ये रूपांतरित':'Geodesic walked acres converted to hectares'):'',age,data.crop_age_days?(marathi?'डेटासेटमधील पीक वय':'Crop age field'):age?(marathi?'२२ ऑक्टोबर २०२६ चे सर्वेक्षणातील वय':'True crop age as of 22 Oct 2026'):'',data.predicted_pol_juice_pct,data.predicted_brix_bx,data.predicted_ccs_pct,recoveryForExport(data.predicted_ccs_pct),data['Standing Millable Tonnage (MT)'],marathi?(row.status==='Harvested'?'तोडणी पूर्ण':'तोडणी बाकी'):row.status,row.sourceTimestamp,data['True Crop Age as of Oct 22 (Days)'],RECOVERY_FACTOR,data.satellite_acquisition_date,data.satellite_refresh_status,data.prediction_refresh_status,data.optical_ndvi,data.optical_ndre,data.clear_sky_coverage_pct,data.detected_cane_area_ha,data.tonnage_basis,data.input_provenance_policy,data.quality_model_variant,data.quality_input_count,data.ccs_basis,data.weather_last_date,data.s1_date_max,data.quality_validation_status];
                return values.map(quote).join(',');
              });
              controller.enqueue(encoder.encode(`${lines.join('\r\n')}\r\n`));
              cursor += batch.length;
            }
            controller.close();
          } catch (error) { controller.error(error); }
        },
      });
      return new Response(stream, { headers: { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename="gangamai_satellite_register.csv"', 'Cache-Control': 'private, no-store' } });
    }
    const [summaryRows, filteredCountRows, pageRows] = await Promise.all([
      db.select({
        total: sql<number>`count(*)`,
        unharvested: sql<number>`sum(case when ${satelliteRegister.status} = 'Unharvested' then 1 else 0 end)`,
        harvested: sql<number>`sum(case when ${satelliteRegister.status} = 'Harvested' then 1 else 0 end)`,
        incomplete: sql<number>`sum(case when ${satelliteRegister.complete} = 0 and ${satelliteRegister.status} = 'Unharvested' then 1 else 0 end)`,
      }).from(satelliteRegister).where(current),
      db.select({ total: sql<number>`count(*)` }).from(satelliteRegister).where(where),
      db.select({ plotNo: satelliteRegister.plotNo, status: satelliteRegister.status, complete: satelliteRegister.complete, sourceTimestamp: satelliteRegister.sourceTimestamp, dataJson: satelliteRegister.dataJson })
        .from(satelliteRegister).where(where).orderBy(asc(satelliteRegister.plotNo)).limit(limit).offset(offset),
    ]);
    const summary = summaryRows[0] || { total: 0, unharvested: 0, harvested: 0, incomplete: 0 };
    const filteredTotal = Number(filteredCountRows[0]?.total || 0);
    return json({ summary, filteredTotal, rows: pageRows.map(row => ({ ...row, complete: Boolean(row.complete), data: JSON.parse(row.dataJson) })), offset, limit, hasMore: offset + pageRows.length < filteredTotal });
  } catch {
    return json({ error: 'Satellite register is not available yet. Please refresh shortly.' }, 503);
  }
}

const importedRow = z.object({
  plotNo: z.string().trim().min(1).max(120),
  sourceTimestamp: z.string().trim().min(1).max(80),
  data: z.record(z.string(), z.unknown()),
});

export async function POST(request: Request) {
  const user = await getMillUser();
  if (!user) return json({ error: 'Sign in required' }, 401);
  const origin = request.headers.get('origin');
  if (!origin || origin !== new URL(request.url).origin) return json({ error: 'Invalid request origin' }, 403);
  if (Number(request.headers.get('content-length') || 0) > 3_000_000) return json({ error: 'Import batch too large' }, 413);
  try {
    const raw = await request.text();
    if (raw.length > 3_000_000) return json({ error: 'Import batch too large' }, 413);
    const body = JSON.parse(raw) as Record<string, unknown>;
    const db = getDb();
    const ownerId = user.userId;
    const mill = await db.select({ ownerId: mills.ownerId }).from(mills).where(eq(mills.ownerId, ownerId)).limit(1);
    if (!mill.length && ownerId !== 'mill_gangamai_sugar') return json({ error: 'Set up your mill first' }, 409);

    if (body.action === 'import') {
      const v = z.object({ snapshotId: z.string().uuid(), rows: z.array(importedRow).min(1).max(500) }).parse(body);
      if (new Set(v.rows.map(row => row.plotNo)).size !== v.rows.length) return json({ error: 'Duplicate plot numbers in this upload batch.' }, 400);
      const importedAt = new Date().toISOString();
      const statements = v.rows.map(row => {
        const registeredArea = String(row.data.registered_area_ha ?? '').trim();
        const walkedAcres = String(row.data['Geodesic Walked Acres'] ?? '').trim();
        const areaText = registeredArea || walkedAcres;
        const ageText = String(row.data.crop_age_days ?? '').trim() || String(row.data['True Crop Age as of Oct 22 (Days)'] ?? '').trim();
        const area = Number(areaText);
        const age = Number(ageText);
        const complete = Boolean(areaText && ageText) && Number.isFinite(area) && area > 0 && Number.isFinite(age) && age >= 0;
        return db.insert(satelliteRegister).values({
          id: crypto.randomUUID(), ownerId, snapshotId: v.snapshotId, plotNo: row.plotNo,
          status: 'Unharvested', complete: complete ? 1 : 0, sourceTimestamp: row.sourceTimestamp,
          dataJson: JSON.stringify(row.data), isCurrent: 0, importedAt,
        }).onConflictDoUpdate({
          target: [satelliteRegister.ownerId, satelliteRegister.snapshotId, satelliteRegister.plotNo],
          set: { status: 'Unharvested', complete: complete ? 1 : 0, sourceTimestamp: row.sourceTimestamp, dataJson: JSON.stringify(row.data), importedAt },
        });
      });
      await db.batch(statements as [typeof statements[number], ...typeof statements[number][]]);
      return json({ ok: true, count: v.rows.length });
    }

    if (body.action === 'finalize') {
      const v = z.object({ snapshotId: z.string().uuid(), expectedCount: z.number().int().positive().max(50000), confirmedHarvestedCount: z.literal(410) }).parse(body);
      const imported = await db.select({ plotNo: satelliteRegister.plotNo, complete: satelliteRegister.complete }).from(satelliteRegister)
        .where(and(eq(satelliteRegister.ownerId, ownerId), eq(satelliteRegister.snapshotId, v.snapshotId), eq(satelliteRegister.status, 'Unharvested')));
      if (imported.length !== v.expectedCount) return json({ error: `Only ${imported.length.toLocaleString()} of ${v.expectedCount.toLocaleString()} rows are staged; the active register was not changed.` }, 409);
      const importedNumbers = new Set(imported.map(row => row.plotNo));
      const registeredPlots = await db.select().from(plots).where(eq(plots.ownerId, ownerId));
      const harvested = registeredPlots.filter(plot => !importedNumbers.has(plot.plotNo));
      if (harvested.length !== v.confirmedHarvestedCount) return json({ error: `Found ${harvested.length} registered plots missing from the new unharvested list; expected the 410 you confirmed. No active dataset was switched.` }, 409);
      const importedAt = new Date().toISOString();
      const archiveStatements = harvested.map(plot => db.insert(satelliteRegister).values({
        id: crypto.randomUUID(), ownerId, snapshotId: v.snapshotId, plotNo: plot.plotNo,
        status: 'Harvested', complete: 1, sourceTimestamp: 'Not supplied',
        dataJson: JSON.stringify({ plotNo: plot.plotNo, village: plot.village, variety: plot.variety, caneType: plot.caneType, registered_area_ha: plot.area, planting_date: plot.plantingDate, archive_note: 'Retained from the previous register; user confirmed harvested.' }),
        isCurrent: 0, importedAt,
      }).onConflictDoUpdate({
        target: [satelliteRegister.ownerId, satelliteRegister.snapshotId, satelliteRegister.plotNo],
        set: { status: 'Harvested', complete: 1, sourceTimestamp: 'Not supplied', dataJson: JSON.stringify({ plotNo: plot.plotNo, village: plot.village, variety: plot.variety, caneType: plot.caneType, registered_area_ha: plot.area, planting_date: plot.plantingDate, archive_note: 'Retained from the previous register; user confirmed harvested.' }), importedAt },
      }));
      if (archiveStatements.length) await db.batch(archiveStatements as [typeof archiveStatements[number], ...typeof archiveStatements[number][]]);
      await db.batch([
        db.update(satelliteRegister).set({ isCurrent: 0 }).where(and(eq(satelliteRegister.ownerId, ownerId), eq(satelliteRegister.isCurrent, 1))),
        db.update(satelliteRegister).set({ isCurrent: 1 }).where(and(eq(satelliteRegister.ownerId, ownerId), eq(satelliteRegister.snapshotId, v.snapshotId))),
      ]);
      return json({ ok: true, unharvested: imported.length, harvestedArchived: harvested.length, incomplete: imported.filter(row => !row.complete).length });
    }
    return json({ error: 'Unknown import action' }, 400);
  } catch (error) {
    if (error instanceof z.ZodError) return json({ error: error.issues[0]?.message || 'Invalid import data' }, 400);
    if (error instanceof SyntaxError) return json({ error: 'Invalid import request' }, 400);
    return json({ error: 'Import failed; the previous active register is unchanged. Please retry.' }, 503);
  }
}
