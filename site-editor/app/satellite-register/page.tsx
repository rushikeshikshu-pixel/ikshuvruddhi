import { Activity, Satellite } from 'lucide-react';
import { eq } from 'drizzle-orm';
import { getDb } from '../../db';
import { mills } from '../../db/schema';
import { requireMillUser } from '../session-auth';
import WorkspaceShell from '../ui/workspace-shell';
import SatelliteRegister from '../ui/satellite-register';

export const dynamic = 'force-dynamic';

export default async function SatelliteRegisterPage() {
  const user = await requireMillUser('/satellite-register');
  const db = getDb();
  const mill = await db.select({ name: mills.name, location: mills.location }).from(mills).where(eq(mills.ownerId, user.userId)).limit(1);
  return <WorkspaceShell kind="register" name={mill[0]?.name || 'Gangamai'} location={mill[0]?.location || 'IKSHU INTELLIGENCE'}><SatelliteRegister/></WorkspaceShell>;
}
