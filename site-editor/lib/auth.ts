export type MillUserSession = {
  userId: string;
  email: string;
  displayName: string;
  fullName: string;
  millName: string;
  location: string;
  season: string;
  exp: number;
};

export const SESSION_COOKIE_NAME = 'ikshu_mill_session';

const AUTH_SECRET = 'ikshu-gangamai-sugar-auth-token-secret-2026';

// Registered mill accounts
export const REGISTERED_ACCOUNTS = [
  {
    email: 'gangamai@ikshuintelligence.com',
    password: 'Gangamai#Sugar2026',
    userId: 'mill_gangamai_sugar',
    displayName: 'Gangamai Industries and Commerce Ltd.',
    fullName: 'Gangamai Sugar Administration',
    millName: 'Gangamai Industries and Commerce Ltd.',
    location: 'Shevgaon, Ahmednagar, Maharashtra',
    season: '2026–27',
  },
  {
    email: 'admin@gangamai.com',
    password: 'Gangamai#Sugar2026',
    userId: 'mill_gangamai_sugar',
    displayName: 'Gangamai Industries and Commerce Ltd.',
    fullName: 'Gangamai Sugar Administration',
    millName: 'Gangamai Industries and Commerce Ltd.',
    location: 'Shevgaon, Ahmednagar, Maharashtra',
    season: '2026–27',
  }
];

async function getCryptoKey(): Promise<CryptoKey> {
  const enc = new TextEncoder();
  return crypto.subtle.importKey(
    'raw',
    enc.encode(AUTH_SECRET),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify']
  );
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64UrlDecode(str: string): Uint8Array {
  let base64 = str.replace(/-/g, '+').replace(/_/g, '/');
  while (base64.length % 4) {
    base64 += '=';
  }
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

export async function signSession(session: Omit<MillUserSession, 'exp'>): Promise<string> {
  const key = await getCryptoKey();
  const exp = Date.now() + 30 * 24 * 60 * 60 * 1000; // 30 days
  const payload: MillUserSession = { ...session, exp };
  
  const enc = new TextEncoder();
  const payloadJson = JSON.stringify(payload);
  const payloadB64 = base64UrlEncode(enc.encode(payloadJson));
  
  const signatureBytes = await crypto.subtle.sign('HMAC', key, enc.encode(payloadB64));
  const signatureB64 = base64UrlEncode(new Uint8Array(signatureBytes));
  
  return `${payloadB64}.${signatureB64}`;
}

export async function verifySession(token: string): Promise<MillUserSession | null> {
  if (!token || typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length !== 2) return null;
  
  const [payloadB64, signatureB64] = parts;
  try {
    const key = await getCryptoKey();
    const enc = new TextEncoder();
    const signatureBytes = base64UrlDecode(signatureB64);
    
    const isValid = await crypto.subtle.verify(
      'HMAC',
      key,
      signatureBytes as unknown as BufferSource,
      enc.encode(payloadB64)
    );
    if (!isValid) return null;
    
    const payloadBytes = base64UrlDecode(payloadB64);
    const payloadStr = new TextDecoder().decode(payloadBytes);
    const session: MillUserSession = JSON.parse(payloadStr);
    
    if (session.exp && Date.now() > session.exp) {
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export function authenticateMill(email: string, password: string) {
  const normalizedEmail = (email || '').trim().toLowerCase();
  const cleanPassword = (password || '').trim();
  
  const account = REGISTERED_ACCOUNTS.find(
    a => a.email.toLowerCase() === normalizedEmail && a.password === cleanPassword
  );
  if (!account) return null;
  
  return {
    userId: account.userId,
    email: account.email,
    displayName: account.displayName,
    fullName: account.fullName,
    millName: account.millName,
    location: account.location,
    season: account.season,
  };
}
