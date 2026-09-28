import { randomBytes } from "node:crypto";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { config } from "./config.js";

export interface UserPayload {
  id: string;
  email: string;
  role: "user" | "admin";
}

export interface OAuthStatePayload {
  redirectUri: string;
  nonce: string;
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
