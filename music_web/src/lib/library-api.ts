import type { StreamTrack, Paginated } from '@/lib/streaming-api';

async function libraryFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: 'include',
    headers: {
      'X-Portal-Context': 'user',
      ...(init?.headers ?? {}),
    },
    ...init,
  });
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
