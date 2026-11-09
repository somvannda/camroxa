/**
 * Desktop Google sign-in hand-off.
 *
 * The desktop studio uses the same Google client and the same registered https
 * redirect as the website, so this page is what receives Google's callback for
 * both. A `desktop_port` in the (signed) state means a native client is waiting
 * on a loopback listener: forward the browser there and let the app exchange the
 * code. The payload is only read for routing; the API verifies the signature
 * before it accepts the code.
 */

const LOOPBACK_CALLBACK_PATH = '/google/callback';

export function desktopHandoffPort(state: string | null | undefined): number | null {
  if (!state) return null;
  const segment = state.split('.')[1];
  if (!segment) return null;
  try {
    const base64 = segment.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded)) as { desktop_port?: unknown };
    const port = Number(payload?.desktop_port);
    if (!Number.isInteger(port) || port < 1 || port > 65535) return null;
    return port;
  } catch {
    return null;
  }
}

export function desktopHandoffUrl(
  port: number,
  params: { code?: string | null; state?: string | null; error?: string | null },
): string {
  const query = new URLSearchParams();
  if (params.code) query.set('code', params.code);
  if (params.state) query.set('state', params.state);
  if (params.error) query.set('error', params.error);
  const suffix = query.toString();
  return `http://127.0.0.1:${port}${LOOPBACK_CALLBACK_PATH}${suffix ? `?${suffix}` : ''}`;
}
