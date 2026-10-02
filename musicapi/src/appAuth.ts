import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { config } from "./config.js";

export interface UserPayload {
  id: string;
  email: string;
  role: "user" | "admin";
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
