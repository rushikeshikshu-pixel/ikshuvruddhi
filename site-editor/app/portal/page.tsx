import { requireMillUser } from "../session-auth";
import Portal from "../ui/portal-dashboard";
export const dynamic = "force-dynamic";
export default async function Page(){const user=await requireMillUser('/portal');return <Portal email={user.email} demo={false}/>}



