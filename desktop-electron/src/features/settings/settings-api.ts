import { apiRequest } from "../../lib/api";
import type { ChannelProfile, UserMe } from "../dashboard/account-types";

/**
 * Settings API surface.
 *
 * Endpoints come from the current `platform_api` OpenAPI document:
 * - GET/POST `/profiles`, PUT/DELETE `/profiles/{id}` (update is PUT, not PATCH)
 * - GET/PATCH `/settings`
 * - GET `/youtube/connections`, POST `/youtube/profiles/{id}/connect`,
 *   DELETE `/youtube/profiles/{id}/connection`,
 *   POST `/youtube/connect-sessions/{session_id}/select-channel`
 * - GET/POST `/youtube/profiles/{id}/playlists`
 *
 * Responses are guarded so a malformed or older payload degrades to an empty
 * shape instead of crashing the page.
 */

export type SettingsMap = Record<string, unknown>;

export interface YouTubeChannelOption {
  id: string;
  title: string;
}

export interface YouTubeConnection {
  profile_id: string;
  profile_name: string;
  status: string;
  channel_id: string | null;
  channel_title: string | null;
  session_id: string | null;
  channels: YouTubeChannelOption[];
  message: string | null;
}

export interface YouTubePlaylist {
  id: string;
  title: string;
}

export interface StartYouTubeConnection {
  session_id: string;
  auth_url: string;
  status: string;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function normalizeConnection(value: unknown): YouTubeConnection | null {
  const record = asRecord(value);
  const profileId = asString(record.profile_id);
  if (!profileId) return null;
  const channels = Array.isArray(record.channels)
    ? record.channels
        .map((item) => {
          const channel = asRecord(item);
          const id = asString(channel.id);
          if (!id) return null;
          return { id, title: asString(channel.title) ?? id };
        })
        .filter((item): item is YouTubeChannelOption => Boolean(item))
    : [];
  return {
    profile_id: profileId,
    profile_name: asString(record.profile_name) ?? "",
    status: asString(record.status) ?? "not_connected",
    channel_id: asString(record.channel_id),
    channel_title: asString(record.channel_title),
    session_id: asString(record.session_id),
    channels,
    message: asString(record.message),
  };
}

export async function fetchProfiles(): Promise<ChannelProfile[]> {
  const data = await apiRequest<unknown>({ method: "GET", path: "/profiles" });
  return Array.isArray(data) ? (data as ChannelProfile[]) : [];
}

export async function fetchMe(): Promise<UserMe> {
  return apiRequest<UserMe>({ method: "GET", path: "/users/me" });
}

export async function createProfile(payload: Record<string, unknown>): Promise<ChannelProfile> {
  return apiRequest<ChannelProfile>({ method: "POST", path: "/profiles", body: payload });
}

export async function updateProfile(
  profileId: string,
  payload: Record<string, unknown>,
): Promise<ChannelProfile> {
  return apiRequest<ChannelProfile>({
    method: "PUT",
    path: `/profiles/${encodeURIComponent(profileId)}`,
    body: payload,
  });
}

export async function deleteProfile(profileId: string): Promise<void> {
  await apiRequest<unknown>({
    method: "DELETE",
    path: `/profiles/${encodeURIComponent(profileId)}`,
  });
}

export async function fetchSettings(): Promise<SettingsMap> {
  const data = await apiRequest<unknown>({ method: "GET", path: "/settings" });
  return asRecord(data);
}

export async function patchSettings(patch: Record<string, unknown>): Promise<SettingsMap> {
  const data = await apiRequest<unknown>({ method: "PATCH", path: "/settings", body: patch });
  return asRecord(data);
}

export async function fetchYoutubeConnections(): Promise<YouTubeConnection[]> {
  const data = await apiRequest<unknown>({ method: "GET", path: "/youtube/connections" });
  const record = asRecord(data);
  const items = Array.isArray(record.connections) ? record.connections : [];
  return items
    .map((item) => normalizeConnection(item))
    .filter((item): item is YouTubeConnection => Boolean(item));
}

export async function startYoutubeConnection(profileId: string): Promise<StartYouTubeConnection> {
  const data = await apiRequest<unknown>({
    method: "POST",
    path: `/youtube/profiles/${encodeURIComponent(profileId)}/connect`,
  });
  const record = asRecord(data);
  return {
    session_id: asString(record.session_id) ?? "",
    auth_url: asString(record.auth_url) ?? "",
    status: asString(record.status) ?? "pending_browser",
  };
}

export async function disconnectYoutube(profileId: string): Promise<void> {
  await apiRequest<unknown>({
    method: "DELETE",
    path: `/youtube/profiles/${encodeURIComponent(profileId)}/connection`,
  });
}

export async function selectYoutubeChannel(
  sessionId: string,
  channelId: string,
): Promise<YouTubeConnection | null> {
  const data = await apiRequest<unknown>({
    method: "POST",
    path: `/youtube/connect-sessions/${encodeURIComponent(sessionId)}/select-channel`,
    body: { channel_id: channelId },
  });
  return normalizeConnection(data);
}

export async function fetchPlaylists(profileId: string): Promise<YouTubePlaylist[]> {
  const data = await apiRequest<unknown>({
    method: "GET",
    path: `/youtube/profiles/${encodeURIComponent(profileId)}/playlists`,
  });
  const record = asRecord(data);
  const items = Array.isArray(record.playlists) ? record.playlists : [];
  return items
    .map((item) => {
      const playlist = asRecord(item);
      const id = asString(playlist.id);
      return id ? { id, title: asString(playlist.title) ?? id } : null;
    })
    .filter((item): item is YouTubePlaylist => Boolean(item));
}

export async function createPlaylist(profileId: string, title: string): Promise<YouTubePlaylist | null> {
  const data = await apiRequest<unknown>({
    method: "POST",
    path: `/youtube/profiles/${encodeURIComponent(profileId)}/playlists`,
    body: { title, privacy_status: "private" },
  });
  const record = asRecord(data);
  const id = asString(record.id);
  if (!id) return null;
  return { id, title: asString(record.title) ?? title };
}
