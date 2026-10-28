import { musicAuthFetch } from "@/lib/auth-fetch";

export type SearchTrack = {
  id: string;
  title?: string | null;
  artist_name?: string | null;
  cover_url?: string | null;
  duration_seconds?: number | null;
  play_count?: number | null;
  genre?: string | null;
};

type SearchResponse = {
  items?: SearchTrack[];
  total?: number;
  limit?: number;
  offset?: number;
};

export async function searchPublicTracks(
  query: string,
  limit = 24
): Promise<{ items: SearchTrack[]; total: number }> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  const response = await musicAuthFetch(`/api/v3/public/streaming/search?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Search failed (${response.status})`);
  }
  const data = (await response.json()) as SearchResponse;
  return {
    items: Array.isArray(data.items) ? data.items : [],
    total: Number(data.total ?? 0),
  };
}
