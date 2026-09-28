import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "sunosession";
// Same backend the /backend/* rewrite targets (next.config.ts).
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:4003";

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

  let user: { role?: string; status?: string };
  try {
    const res = await fetch(`${BACKEND_URL}/auth/me`, {
      headers: { cookie: `${SESSION_COOKIE}=${token}` },
      cache: "no-store",
    });
    // Invalid/expired session: drop the dead cookie so the login page starts clean.
    if (!res.ok) return bounce(req, true);
    user = (await res.json()) as { role?: string; status?: string };
  } catch {
    // Backend unreachable — fail closed rather than serving the admin shell.
    return bounce(req);
  }

  if (user.role !== "admin" || user.status !== "active") return bounce(req, true);
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
