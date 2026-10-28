import { env } from 'cloudflare:workers';
import { and, desc, eq, gte, inArray, sql } from 'drizzle-orm';
import { getDb } from '../../../db';
import { plots, boundaries, satelliteObservations, satelliteRequests, mills } from '../../../db/schema';
import { getMillUser } from '../../session-auth';
import { date } from '../../validation';
import { boundaryHash, parseBoundary } from '../../../lib/satellite/geometry';
import { catalogue, measure, SatelliteError } from '../../../lib/satellite/process';
import { predictQuality } from '../../../lib/satellite/predict';
import modelInfo from '../../../lib/satellite/retrained-model-info.json';
import { z } from 'zod';

export const dynamic = 'force-dynamic';
const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { 'Cache-Control': 'private, no-store' } });
const secrets = () => ({ CDSE_CLIENT_ID: env.CDSE_CLIENT_ID, CDSE_CLIENT_SECRET: env.CDSE_CLIENT_SECRET });
const today = () => new Date().toISOString().slice(0, 10);

async function ownsPlot(db: ReturnType<typeof getDb>, ownerId: string, plotId: string) {
  const rows = await db.select().from(plots).where(and(eq(plots.id, plotId), eq(plots.ownerId, ownerId))).limit(1);
  return rows[0];
}

async function consumeRequest(db: ReturnType<typeof getDb>, ownerId: string) {
  const since = Date.now() - 24 * 60 * 60 * 1000;
  const usage = await db.select({ count: sql<number>`count(*)` }).from(satelliteRequests)
    .where(and(eq(satelliteRequests.ownerId, ownerId), gte(satelliteRequests.createdAt, since)));
  if (Number(usage[0]?.count || 0) >= 20) throw new SatelliteError('Daily satellite limit reached (20 catalogue or processing requests). Try again tomorrow.', 429);
  await db.insert(satelliteRequests).values({ id: crypto.randomUUID(), ownerId, createdAt: Date.now() });
}

export async function GET(request: Request) {
  const user = await getMillUser();
  if (!user) return json({ error: 'Sign in to access mill records' }, 401);
  try {
    const db = getDb();
    const ownMill = await db.select({ ownerId: mills.ownerId }).from(mills).where(eq(mills.ownerId, user.userId)).limit(1);
    if (!ownMill.length) return json({ error: 'Set up your mill first' }, 409);
    const plotId = new URL(request.url).searchParams.get('plotId');
    const result: Record<string, unknown> = {
      configured: Boolean(env.CDSE_CLIENT_ID && env.CDSE_CLIENT_SECRET),
      provider: 'Copernicus Data Space Ecosystem',
      model: modelInfo,
      qualityPredictionsEnabled: false,
      predictionNote: modelInfo.predictionNote,
    };
    if (!plotId) {
      const ownBoundaries = await db.select({ plotId: boundaries.plotId, hash: boundaries.hash }).from(boundaries).where(eq(boundaries.ownerId, user.userId));
      return json({ ...result, boundaries: ownBoundaries });
    }
    const plot = await ownsPlot(db, user.userId, plotId);
    if (!plot) return json({ error: 'Plot not found' }, 404);
    const boundary = await db.select().from(boundaries).where(and(eq(boundaries.plotId, plotId), eq(boundaries.ownerId, user.userId))).limit(1);
    const observations = await db.select().from(satelliteObservations)
      .where(and(eq(satelliteObservations.plotId, plotId), eq(satelliteObservations.ownerId, user.userId)))
      .orderBy(desc(satelliteObservations.date)).limit(20);
    return json({ ...result, boundarySaved: Boolean(boundary[0]), boundaryHash: boundary[0]?.hash ?? null, observations: observations.map(row => JSON.parse(row.result)) });
  } catch {
    return json({ error: 'Satellite workspace is temporarily unavailable. Please retry.' }, 503);
  }
}

export async function POST(request: Request) {
  const user = await getMillUser();
  if (!user) return json({ error: 'Sign in required' }, 401);
  const origin = request.headers.get('origin');
  if (!origin || origin !== new URL(request.url).origin) return json({ error: 'Invalid request origin' }, 403);
  if (Number(request.headers.get('content-length') || 0) > 3000000) return json({ error: 'Request too large' }, 413);
  try {
    const body: any = await request.json();
    const db = getDb();
    const ownerId = user.userId;
    const plotId = z.string().min(1).max(120).parse(body.plotId);
    const plot = await ownsPlot(db, ownerId, plotId);
    if (!plot) return json({ error: 'Plot not found' }, 404);

    if (body.action === 'boundary') {
      const geometry = parseBoundary(body.geometry);
      const hash = await boundaryHash(geometry);
      await db.insert(boundaries).values({ plotId, ownerId, geometry: JSON.stringify(geometry), hash, updatedAt: new Date().toISOString() })
        .onConflictDoUpdate({ target: boundaries.plotId, set: { ownerId, geometry: JSON.stringify(geometry), hash, updatedAt: new Date().toISOString() } });
      return json({ ok: true, hash });
    }

    if (body.action === 'boundaryImport') {
      const rows = z.array(z.object({ plotNo: z.string().trim().min(1).max(120), geometry: z.unknown() })).min(1).max(500).parse(body.features);
      if (new Set(rows.map(row => row.plotNo)).size !== rows.length) return json({ error: 'Each plot number must appear once in the boundary file.' }, 400);
      const ownPlots: {id:string;plotNo:string}[] = [];
      for(let offset=0;offset<rows.length;offset+=80)ownPlots.push(...await db.select({id:plots.id,plotNo:plots.plotNo}).from(plots).where(and(eq(plots.ownerId,ownerId),inArray(plots.plotNo,rows.slice(offset,offset+80).map(row=>row.plotNo)))));
      const plotByNo = new Map(ownPlots.map(row => [row.plotNo, row.id]));
      const now = new Date().toISOString();
      const values = await Promise.all(rows.map(async row => {
        const id = plotByNo.get(row.plotNo);
        if (!id) throw new Error('UNMATCHED PLOT: ' + row.plotNo);
        const geometry = parseBoundary(row.geometry);
        return { plotId: id, ownerId, geometry: JSON.stringify(geometry), hash: await boundaryHash(geometry), updatedAt: now };
      }));
      const operations = values.map(value => db.insert(boundaries).values(value).onConflictDoUpdate({ target: boundaries.plotId, set: { ownerId, geometry: value.geometry, hash: value.hash, updatedAt: now } }));
      await db.batch(operations as [typeof operations[number], ...typeof operations[number][]]);
      return json({ ok: true, count: values.length });
    }

    if (!env.CDSE_CLIENT_ID || !env.CDSE_CLIENT_SECRET) return json({ error: 'Copernicus Data Space credentials are not configured for this site yet.' }, 503);
    const saved = await db.select().from(boundaries).where(and(eq(boundaries.plotId, plotId), eq(boundaries.ownerId, ownerId))).limit(1);
    if (!saved[0]) return json({ error: 'Add a plot boundary before searching for imagery.' }, 409);
    const geometry = parseBoundary(JSON.parse(saved[0].geometry));

    if (body.action === 'catalogue') {
      const v = z.object({ sensor: z.enum(['S1', 'S2']), date: date.optional() }).parse(body);
      if (v.date && (v.date < plot.plantingDate || v.date > today())) return json({ error: 'Choose an acquisition date between planting and today.' }, 400);
      await consumeRequest(db, ownerId);
      return json({ scenes: await catalogue(geometry, v.sensor, secrets(), v.date) });
    }

    if (body.action === 'measure') {
      const v = z.object({ sensor: z.enum(['S1', 'S2']), sceneId: z.string().min(1).max(300), date: date, datetime: z.string().datetime(), cloud: z.number().min(0).max(100).nullable().optional(), orbit: z.number().int().nullable().optional(), direction: z.string().max(40).nullable().optional() }).parse(body);
      if (v.date < plot.plantingDate || v.date > today()) return json({ error: 'Choose an acquisition between planting and today.' }, 400);
      const ownCane = { plantingDate: plot.plantingDate, variety: plot.variety, caneType: plot.caneType };
      const existing = await db.select().from(satelliteObservations).where(and(
        eq(satelliteObservations.ownerId, ownerId), eq(satelliteObservations.plotId, plotId), eq(satelliteObservations.date, v.date), eq(satelliteObservations.sensor, v.sensor), eq(satelliteObservations.boundaryHash, saved[0].hash),
      )).limit(1);
      if (existing[0]) return json({ observation: JSON.parse(existing[0].result), cached: true });
      await consumeRequest(db, ownerId);
      const observation = await measure(geometry, { id: v.sceneId, date: v.date, datetime: v.datetime, sensor: v.sensor, cloud: v.cloud ?? null, orbit: v.orbit ?? null, direction: v.direction ?? null }, secrets());
      const prediction = v.sensor === 'S2' ? predictQuality(observation as any, ownCane, geometry) : null;
      const record = { ...observation, prediction };
      await db.insert(satelliteObservations).values({ id: crypto.randomUUID(), ownerId, plotId, date: v.date, sensor: v.sensor, boundaryHash: saved[0].hash, result: JSON.stringify(record), createdAt: new Date().toISOString() })
        .onConflictDoUpdate({ target: [satelliteObservations.ownerId, satelliteObservations.plotId, satelliteObservations.date, satelliteObservations.sensor, satelliteObservations.boundaryHash], set: { result: JSON.stringify(record), createdAt: new Date().toISOString() } });
      if (observation.sensor === 'S2' && observation.status === 'Screened optical observation') {
        await db.update(plots).set({ acquisitionDate: v.date, cloud: v.cloud ?? null, ndvi: observation.ndvi }).where(and(eq(plots.id, plotId), eq(plots.ownerId, ownerId)));
      }
      return json({ observation: record, cached: false });
    }
    return json({ error: 'Unknown satellite action' }, 400);
  } catch (error) {
    if (error instanceof z.ZodError) return json({ error: error.issues[0]?.message || 'Invalid satellite request' }, 400);
    if (error instanceof SatelliteError) return json({ error: error.message }, error.status);
    if (error instanceof SyntaxError) return json({ error: 'Invalid boundary data' }, 400);
    if (String(error).includes('UNIQUE')) return json({ error: 'This satellite observation already exists.' }, 409);
    return json({ error: 'Satellite processing failed. No observation was saved. Please retry later.' }, 502);
  }
}

