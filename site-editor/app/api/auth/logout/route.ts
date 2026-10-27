import { SESSION_COOKIE_NAME } from '../../../../lib/auth';

export const dynamic = 'force-dynamic';

function clearSession(request: Request) {
  const url = new URL(request.url);
  const returnTo = url.searchParams.get('return_to') || '/login';
  const cookieHeader = `${SESSION_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`;

  return new Response(null, {
    status: 302,
    headers: {
      Location: returnTo,
      'Set-Cookie': cookieHeader,
    },
  });
}

export async function GET(request: Request) {
  return clearSession(request);
}

export async function POST(request: Request) {
  return clearSession(request);
}
