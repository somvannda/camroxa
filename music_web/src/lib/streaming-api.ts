function resolveApiBase(): string {
  // Browser: always same-origin so nginx /api proxy sets/sends music.* cookies.
  if (typeof window !== 'undefined') {
    return '';
  }
  return (
    process.env.STREAMING_API_BASE_URL?.replace(/\/$/, '') ||
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '') ||
    process.env.PLATFORM_API_BASE_URL?.replace(/\/$/, '') ||
    'http://127.0.0.1:8000'
  );
}

const API_BASE = resolveApiBase();

export function getStreamingApiBase(): string {
  if (typeof window !== 'undefined') return '';
  return API_BASE;
}

async function fetchJson<T>(path: string): Promise<T> {
  const base = typeof window !== 'undefined' ? '' : API_BASE;
  const response = await fetch(`${base}${path}`, {
    credentials: typeof window !== 'undefined' ? 'include' : 'omit',
    ...(typeof window === 'undefined' ? { next: { revalidate: 30 } } : {}),
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type StreamTrack = {
  id: string;
  title: string;
  album_id?: string;
  user_id?: string;
  album_name?: string;
  artist_name?: string;
  variant?: string;
  cover_url?: string | null;
  genre?: string | null;
  genres?: string[];
  duration_seconds?: number | null;
  play_count?: number;
  lyrics?: string | null;
  play_url?: string | null;
  published_at?: string | null;
  created_at?: string | null;
  added_at?: string | null;
};

export type StreamAlbum = {
  id: string;
  album_name: string;
  artist_name?: string;
  user_id?: string;
  cover_url?: string | null;
  track_count?: number;
  play_count?: number;
  genre?: string | null;
  genres?: string[];
};

export type StreamArtist = {
  user_id: string;
  artist_name?: string | null;
  avatar_url?: string | null;
  album_count?: number;
  track_count?: number;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return '';
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

export function formatPlayCount(count?: number | null): string {
  const n = Math.max(0, Math.floor(Number(count) || 0));
  return n.toLocaleString();
}

export function formatGenreLabels(track: {
  genres?: string[] | null;
  genre?: string | null;
}): string {
  if (track.genres?.length) return track.genres.join(' · ');
  return track.genre?.trim() ?? '';
}

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

export async function listAlbums(limit = 24, offset = 0) {
  return fetchJson<Paginated<StreamAlbum>>(
    `/api/v1/public/streaming/albums?limit=${limit}&offset=${offset}`,
  );
}

export async function listArtists(limit = 48, offset = 0) {
  return fetchJson<Paginated<StreamArtist>>(
    `/api/v1/public/streaming/artists?limit=${limit}&offset=${offset}`,
  );
}

export async function searchCatalog(query: string, limit = 24, offset = 0) {
  const q = encodeURIComponent(query);
  return fetchJson<Paginated<StreamTrack>>(
    `/api/v1/public/streaming/search?q=${q}&limit=${limit}&offset=${offset}`,
  );
}

export async function getAlbum(albumId: string) {
  return fetchJson<StreamAlbum & { tracks: StreamTrack[] }>(
    `/api/v1/public/streaming/albums/${albumId}`,
  );
}

export async function getArtist(userId: string) {
  return fetchJson<{ user_id: string; artist_name?: string; albums: StreamAlbum[] }>(
    `/api/v1/public/streaming/artists/${userId}`,
  );
}

export async function getPlayUrl(trackId: string) {
  return fetchJson<{
    url: string;
    title?: string;
    album_id?: string | null;
    album_name?: string;
    user_id?: string | null;
    artist_name?: string;
    cover_url?: string | null;
    duration_seconds?: number | null;
    play_count?: number;
    genre?: string | null;
    lyrics?: string | null;
  }>(`/api/v1/public/streaming/tracks/${trackId}/play-url`);
}

export async function getGenres() {
  return fetchJson<{ items: StreamGenre[] }>('/api/v1/public/streaming/genres');
}

export async function getGenre(slug: string) {
  return fetchJson<StreamGenreDetail>(`/api/v1/public/streaming/genres/${slug}`);
}
