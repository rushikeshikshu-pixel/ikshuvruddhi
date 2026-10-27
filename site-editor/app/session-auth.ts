import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { verifySession, SESSION_COOKIE_NAME } from "../lib/auth";

export type MillUser = {
  userId: string;
  displayName: string;
  email: string;
  fullName: string | null;
};

export async function getMillUser(): Promise<MillUser | null> {
  try {
    const cookieStore = await cookies();
    const sessionToken = cookieStore.get(SESSION_COOKIE_NAME)?.value;
    if (!sessionToken) return null;
    const user = await verifySession(sessionToken);
    if (!user) return null;
    return {
      userId: user.userId,
      displayName: user.displayName,
      email: user.email,
      fullName: user.fullName,
    };
  } catch {
    return null;
  }
}

export async function requireMillUser(returnTo: string): Promise<MillUser> {
  const user = await getMillUser();
  if (user) return user;
  const safeReturnTo = returnTo.startsWith('/') && !returnTo.startsWith('//') ? returnTo : '/portal';
  redirect(`/login?return_to=${encodeURIComponent(safeReturnTo)}`);
}
