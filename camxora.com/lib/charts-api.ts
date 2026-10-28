import { musicAuthFetch } from "@/lib/auth-fetch";

export type ChartTrack = {
  id: string;
  title: string;
  artist_name: string;
  cover_url?: string | null;
  play_url?: string | null;
  play_count?: number | null;
  genre?: string | null;
  style?: string | null;
  added_at?: string | null;
  playlist_name?: string | null;
};

type RecentTracksResponse = {
  items?: ChartTrack[];
  total?: number;
};

export async function fetchChartTracks(limit = 100): Promise<ChartTrack[]> {
  const response = await musicAuthFetch(
    `/api/v3/web-music/public/tracks/recent?limit=${limit}`
  );
  if (!response.ok) {
    throw new Error(`Could not load charts (${response.status})`);
  }
  const data = (await response.json()) as RecentTracksResponse;
  return Array.isArray(data.items) ? data.items : [];
}
