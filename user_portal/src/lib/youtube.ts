"use client";

import { platformJson } from "@/lib/auth-fetch";

export type YouTubeChannelOption = {
  id: string;
  title: string;
};

export type YouTubeConnection = {
  profile_id: string;
  profile_name: string;
  status: string;
  channel_id?: string | null;
  channel_title?: string | null;
  session_id?: string | null;
  channels?: YouTubeChannelOption[];
  message?: string | null;
};

export type StartYouTubeConnectionResponse = {
  session_id: string;
  auth_url: string;
  status: string;
};

export async function listYouTubeConnections(): Promise<YouTubeConnection[]> {
  const result = await platformJson<{ connections: YouTubeConnection[] }>({
    path: "/youtube/connections",
    method: "GET",
  });
  return result.connections ?? [];
}

export async function startYouTubeConnection(profileId: string): Promise<StartYouTubeConnectionResponse> {
  return platformJson<StartYouTubeConnectionResponse>({
    path: `/youtube/profiles/${encodeURIComponent(profileId)}/connect`,
    method: "POST",
  });
}

export async function resyncYouTubeConnection(profileId: string): Promise<YouTubeConnection> {
  return platformJson<YouTubeConnection>({
    path: `/youtube/profiles/${encodeURIComponent(profileId)}/resync`,
    method: "POST",
  });
}

export async function disconnectYouTubeConnection(profileId: string): Promise<{ message: string }> {
  return platformJson<{ message: string }>({
    path: `/youtube/profiles/${encodeURIComponent(profileId)}/connection`,
    method: "DELETE",
  });
}
