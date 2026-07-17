function resolveApiBase(): string {
  const publicBase = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '');
  if (publicBase) return publicBase;

  // Server components can reach the API directly on the same host.
  if (typeof window === 'undefined') {
    return (
      process.env.STREAMING_API_BASE_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8100'
    );
  }

  // Browser uses same-origin /api when nginx proxies to platform_api.
  return '';
}

const API_BASE = resolveApiBase();

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { next: { revalidate: 30 } });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type StreamTrack = {
  id: string;
  title: string;
  album_name?: string;
  artist_name?: string;
  variant?: string;
  cover_url?: string | null;
  genre?: string | null;
  duration_seconds?: number | null;
  lyrics?: string | null;
};

export type StreamAlbum = {
  id: string;
  album_name: string;
  artist_name?: string;
  cover_url?: string | null;
  track_count?: number;
  genre?: string | null;
};

function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return '';
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

export { formatDuration };

export type StreamGenre = {
  genre: string;
  slug: string;
  album_count: number;
  track_count: number;
};

export type StreamGenreDetail = StreamGenre & {
  albums: StreamAlbum[];
  tracks: StreamTrack[];
};

export async function getStreamingHome() {
  return fetchJson<{ recent_tracks: StreamTrack[]; albums: StreamAlbum[] }>(
    '/api/v1/public/streaming/home',
  );
}

export async function getAlbum(albumId: string) {
  return fetchJson<StreamAlbum & { tracks: StreamTrack[] }>(
    `/api/v1/public/streaming/albums/${albumId}`,
  );
}

export async function getPlayUrl(trackId: string) {
  return fetchJson<{
    url: string;
    title?: string;
    album_name?: string;
    artist_name?: string;
    cover_url?: string | null;
    duration_seconds?: number | null;
    genre?: string | null;
  }>(`/api/v1/public/streaming/tracks/${trackId}/play-url`);
}

export async function getGenres() {
  return fetchJson<{ items: StreamGenre[] }>('/api/v1/public/streaming/genres');
}

export async function getGenre(slug: string) {
  return fetchJson<StreamGenreDetail>(`/api/v1/public/streaming/genres/${slug}`);
}
