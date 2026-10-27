import { authenticateMill, signSession, SESSION_COOKIE_NAME } from '../../../../lib/auth';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const { email, password } = body as { email?: string; password?: string };

    if (!email || !password) {
      return Response.json(
        { error: 'Please enter both your mill email and password.' },
        { status: 400 }
      );
    }

    const user = authenticateMill(email, password);
    if (!user) {
      return Response.json(
        { error: 'Invalid mill account credentials. Please verify your email and password.' },
        { status: 401 }
      );
    }

    const token = await signSession(user);
    const isProd = process.env.NODE_ENV === 'production';
    const cookieHeader = `${SESSION_COOKIE_NAME}=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000${isProd ? '; Secure' : ''}`;

    return new Response(
      JSON.stringify({
        ok: true,
        user: {
          userId: user.userId,
          email: user.email,
          displayName: user.displayName,
          millName: user.millName,
        },
        redirect: '/portal',
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Set-Cookie': cookieHeader,
        },
      }
    );
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Authentication service error';
    return Response.json({ error: message }, { status: 500 });
  }
}
