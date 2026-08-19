import { musicAuthFetch } from '@/lib/auth-fetch';
import type { StreamTrack, Paginated } from '@/lib/streaming-api';

async function libraryFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await musicAuthFetch(path, init);
  if (!response.ok) {
    throw new Error(`Library request failed: ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function fetchLikedTrackIds(): Promise<string[]> {
  const data = await libraryFetch<{ track_ids: string[] }>(
    '/api/v1/streaming/library/likes/ids',
  );
  return data.track_ids ?? [];
}

export async function fetchLikedTracks(limit = 50, offset = 0): Promise<Paginated<StreamTrack>> {
  return libraryFetch<Paginated<StreamTrack>>(
    `/api/v1/streaming/library/likes?limit=${limit}&offset=${offset}`,
  );
}

export async function likeTrack(trackId: string): Promise<void> {
  await libraryFetch(`/api/v1/streaming/library/likes/${trackId}`, { method: 'PUT' });
}

export async function unlikeTrack(trackId: string): Promise<void> {
  await libraryFetch(`/api/v1/streaming/library/likes/${trackId}`, { method: 'DELETE' });
}

function isWebMusicLikeKey(trackId: string): boolean {
  const parts = trackId.split(':');
  return parts.length === 2 && /^[0-9a-f-]{36}$/i.test(parts[0]);
}

export async function fetchWebMusicLikedKeys(): Promise<string[]> {
  const data = await libraryFetch<{ keys: string[] }>('/api/v1/web-music/likes/keys');
  return data.keys ?? [];
}

export async function likeWebMusicTrack(taskId: string, variant: string): Promise<void> {
  await libraryFetch(
    `/api/v1/web-music/generations/${encodeURIComponent(taskId)}/like?variant=${encodeURIComponent(variant)}`,
    { method: 'PUT' },
  );
}

export async function unlikeWebMusicTrack(taskId: string, variant: string): Promise<void> {
  await libraryFetch(
    `/api/v1/web-music/generations/${encodeURIComponent(taskId)}/like?variant=${encodeURIComponent(variant)}`,
    { method: 'DELETE' },
  );
}

export { isWebMusicLikeKey };
