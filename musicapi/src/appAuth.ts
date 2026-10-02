import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { config } from "./config.js";

export interface UserPayload {
  id: string;
  email: string;
  role: "user" | "admin";
}

/** Name of the browser session cookie holding the signed JWT. */
export const SESSION_COOKIE = "sunosession";

/** Session lifetime, mirrored by the JWT's `expiresIn` in `signToken`. */
const SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60;

/**
 * Serialize the session cookie. `HttpOnly` keeps the JWT out of reach of
 * scripts, `SameSite=Lax` blocks it from riding cross-site POSTs, and `Secure`
 * (set in production) keeps it off plaintext connections.
 */
export function serializeSessionCookie(token: string, secure: boolean): string {
  const attrs = [
    `${SESSION_COOKIE}=${token}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    `Max-Age=${SESSION_MAX_AGE_SECONDS}`,
  ];
  if (secure) attrs.push("Secure");
  return attrs.join("; ");
}

/** Serialize a cookie that tells the browser to drop the session. */
export function serializeClearedSessionCookie(secure: boolean): string {
  const attrs = [`${SESSION_COOKIE}=`, "Path=/", "HttpOnly", "SameSite=Lax", "Max-Age=0"];
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
