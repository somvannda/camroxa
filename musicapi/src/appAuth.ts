import { randomBytes } from "node:crypto";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { config } from "./config.js";

export interface UserPayload {
  id: string;
  email: string;
  role: "user" | "admin";
  /** Session-revocation version; a bump invalidates previously issued tokens. */
  tv?: number;
}

export interface OAuthStatePayload {
  redirectUri: string;
  nonce: string;
}

/** Name of the browser session cookie holding the signed JWT. */
export const SESSION_COOKIE = "sunosession";
/**
 * Admin console session cookie. Cookies are keyed by host (not port), so on
 * `localhost` the user app (:4001) and admin console (:4002) would otherwise
 * share one session and overwrite each other. In production the two live on
 * different subdomains, but a distinct name keeps local dev sane too.
 */
export const SESSION_COOKIE_ADMIN = process.env.SESSION_COOKIE_ADMIN ?? "sunosession_admin";

/** Session lifetime, mirrored by the JWT's `expiresIn` in `signToken`. */
const SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

/**
 * Serialize the session cookie. `HttpOnly` keeps the JWT out of reach of
 * scripts, `SameSite=Lax` blocks it from riding cross-site POSTs, and `Secure`
 * (set in production) keeps it off plaintext connections.
 */
export function serializeSessionCookie(token: string, secure: boolean, name = SESSION_COOKIE): string {
  const attrs = [
    `${name}=${token}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    `Max-Age=${SESSION_MAX_AGE_SECONDS}`,
  ];
  if (secure) attrs.push("Secure");
  return attrs.join("; ");
}

/** Serialize a cookie that tells the browser to drop the session. */
export function serializeClearedSessionCookie(secure: boolean, name = SESSION_COOKIE): string {
  const attrs = [`${name}=`, "Path=/", "HttpOnly", "SameSite=Lax", "Max-Age=0"];
  if (secure) attrs.push("Secure");
  return attrs.join("; ");
}

/** Read a single cookie value out of a raw `Cookie` request header. */
export function readCookie(header: string | undefined, name: string): string | null {
  if (!header) return null;
  for (const part of header.split(";")) {
    const eq = part.indexOf("=");
    if (eq === -1) continue;
    if (part.slice(0, eq).trim() === name) return part.slice(eq + 1).trim();
  }
  return null;
}

/** Read whichever session cookie is present (user app or admin console). */
export function readSessionCookie(header: string | undefined): string | null {
  return readCookie(header, SESSION_COOKIE) ?? readCookie(header, SESSION_COOKIE_ADMIN);
}

export async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, 10);
}

export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash);
}

export function signToken(user: UserPayload): string {
  return jwt.sign(user, config.jwtSecret, { expiresIn: "7d" });
}

export function verifyToken(token: string): UserPayload | null {
  try {
    return jwt.verify(token, config.jwtSecret) as UserPayload;
  } catch {
    return null;
  }
}

// Signed, short-lived OAuth `state`: ties the authorization request to this
// server (CSRF protection) and binds the redirect URI that was validated
// against the allowlist when the flow started, so the callback no longer has
// to trust a client-supplied redirect_uri.
export function signOAuthState(redirectUri: string): string {
  const payload: OAuthStatePayload = { redirectUri, nonce: randomBytes(16).toString("hex") };
  return jwt.sign(payload, config.jwtSecret, { expiresIn: "10m" });
}

export function verifyOAuthState(state: string): OAuthStatePayload | null {
  try {
    const payload = jwt.verify(state, config.jwtSecret) as OAuthStatePayload;
    if (!payload || typeof payload.redirectUri !== "string") return null;
    return payload;
  } catch {
    return null;
  }
}
