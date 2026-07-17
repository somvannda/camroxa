"use client";

import { platformFetch } from "@/lib/auth-fetch";

async function fetchMediaObjectUrl(path: string): Promise<string | null> {
  const response = await platformFetch({
    path,
    method: "GET",
  });

  if (!response.ok) {
    return null;
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function loadProfileLogoObjectUrl(profileId: string): Promise<string | null> {
  return fetchMediaObjectUrl(`/media/channel-profiles/${encodeURIComponent(profileId)}/logo`);
}

export async function loadProfileCoverObjectUrl(profileId: string, index: number): Promise<string | null> {
  return fetchMediaObjectUrl(`/media/channel-profiles/${encodeURIComponent(profileId)}/covers/${index}`);
}
