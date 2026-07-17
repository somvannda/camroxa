"use client";

import { platformJson } from "@/lib/auth-fetch";

export type UserSettings = Record<string, unknown>;

export async function getUserSettings(): Promise<UserSettings> {
  return platformJson<UserSettings>({
    path: "/settings",
    method: "GET",
  });
}

export async function patchUserSettings(patch: Record<string, unknown>): Promise<UserSettings> {
  return platformJson<UserSettings>({
    path: "/settings",
    method: "PATCH",
    body: patch,
  });
}
