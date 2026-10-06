import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, probeAdminSession } from "./lib/adminGuard";

// Same backend the /backend/* rewrite targets (next.config.ts). Prefer the
// literal loopback address over "localhost" so the guard can't fail on a host
// where localhost resolves to IPv6 (::1) while the API binds 127.0.0.1 only.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:4003";

/**
 * Server-side guard for the admin console (Next.js 16 `proxy` convention,
 * formerly `middleware`). The API is the real authority — every `/admin/*`
 * route re-checks the role — but this stops a non-admin from ever rendering
 * the admin shell: the httpOnly session cookie is forwarded to the API's
 * `/auth/me` and anything other than an active admin is bounced to `/login`
 * before the page is served. Previously this was a client-side check against a
 * `localStorage` profile, which any visitor could spoof.
 */
export async function proxy(req: NextRequest) {
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return bounce(req);

  const probe = await probeAdminSession(token, BACKEND_URL);

  // Invalid session, or a valid session that is no longer an active admin:
  // drop the stale cookie so the login page starts clean.
  if (probe.kind === "dead" || probe.kind === "inactive") return bounce(req, true);

  // API unreachable or unhealthy: fail closed (don't serve the shell) but keep
  // the session cookie. Deleting it here was turning a transient backend fault
  // into a permanent logout on the operator's next menu click.
  if (probe.kind === "unavailable") {
    console.warn("[admin-proxy] /auth/me probe unavailable; keeping session cookie.");
    return bounce(req);
  }

  return NextResponse.next();
}

function bounce(req: NextRequest, clearCookie = false): NextResponse {
  const res = NextResponse.redirect(new URL("/login", req.url));
  if (clearCookie) res.cookies.delete(SESSION_COOKIE);
  return res;
}

export const config = {
  // Guard the console and the root landing redirect; /login stays open.
  matcher: ["/", "/admin/:path*"],
};
