import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

function resolveMiddlewareApiBase(request: NextRequest): string {
  const internal = process.env.PLATFORM_API_INTERNAL_URL?.trim();
  if (internal) {
    return internal.replace(/\/$/, "");
  }

  const configured = process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }

  // Loopback API avoids edge middleware TLS/DNS issues on the VPS.
  if (process.env.NODE_ENV === "production") {
    return "http://127.0.0.1:8100/api/v3";
  }

  return `${request.nextUrl.origin}/api/v3`;
}

async function fetchSignupMode(apiBase: string): Promise<"open" | "invite_only" | null> {
  try {
    const response = await fetch(`${apiBase}/auth/signup-mode`, {
      method: "GET",
      headers: { "X-Portal-Context": "user" },
      cache: "no-store",
    });
    if (!response.ok) return null;
    const data = (await response.json()) as { mode?: string };
    if (data.mode === "open") return "open";
    if (data.mode === "invite_only") return "invite_only";
    return null;
  } catch {
    return null;
  }
}

export async function middleware(request: NextRequest) {
  if (request.nextUrl.pathname !== "/invite") {
    return NextResponse.next();
  }

  const mode = await fetchSignupMode(resolveMiddlewareApiBase(request));
  if (mode === "open") {
    return NextResponse.redirect(new URL("/register", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: "/invite",
};
