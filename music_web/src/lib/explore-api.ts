import type { WebMusicPublicArtist, WebMusicPublicRecentTrack } from '@/lib/playlist-api';
import type { StreamArtist, StreamTrack } from '@/lib/streaming-api';

export type ExploreArtist = {
  user_id: string;
  artist_name?: string | null;
  avatar_url?: string | null;
  playlist_count?: number;
  album_count?: number;
  track_count?: number;
};

export function mergeExploreArtists(
  streaming: StreamArtist[],
  webMusic: WebMusicPublicArtist[],
): ExploreArtist[] {
  const map = new Map<string, ExploreArtist>();

  for (const artist of streaming) {
    map.set(artist.user_id, {
      user_id: artist.user_id,
      artist_name: artist.artist_name,
      avatar_url: artist.avatar_url,
      album_count: artist.album_count ?? 0,
      track_count: artist.track_count ?? 0,
    });
  }

  for (const artist of webMusic) {
    const existing = map.get(artist.user_id);
    map.set(artist.user_id, {
      user_id: artist.user_id,
      artist_name: artist.artist_name ?? existing?.artist_name,
      avatar_url: artist.avatar_url ?? existing?.avatar_url,
      playlist_count: artist.playlist_count ?? 0,
      album_count: existing?.album_count ?? 0,
      track_count: Math.max(artist.track_count ?? 0, existing?.track_count ?? 0),
    });
  }

  return Array.from(map.values()).sort((left, right) => {
    const trackDelta = (right.track_count ?? 0) - (left.track_count ?? 0);
    if (trackDelta !== 0) return trackDelta;
    return String(left.artist_name ?? '').localeCompare(String(right.artist_name ?? ''));
  });
}

function trackTimestamp(
  track: StreamTrack & { added_at?: string | null; published_at?: string | null; created_at?: string | null },
): number {
  for (const raw of [track.added_at, track.published_at, track.created_at]) {
    if (!raw) continue;
    const value = Date.parse(String(raw));
    if (!Number.isNaN(value)) return value;
  }
  return 0;
}

export function publicTrackToStreamTrack(track: WebMusicPublicRecentTrack): StreamTrack {
  return {
    id: track.id,
    title: track.title,
    user_id: track.user_id,
    artist_name: track.artist_name,
    album_name: track.playlist_name || undefined,
    genre: track.genre ?? track.style ?? null,
    cover_url: track.cover_url ?? null,
    play_url: track.play_url,
    play_count: track.play_count ?? 0,
    added_at: track.added_at,
    duration_seconds: track.duration_seconds ?? null,
  };
}

export function mergeRecentTracks(
  streaming: StreamTrack[],
  publicTracks: WebMusicPublicRecentTrack[],
  limit = 12,
): StreamTrack[] {
  const merged = [...streaming.map((track) => ({ ...track })), ...publicTracks.map(publicTrackToStreamTrack)];
  merged.sort((left, right) => trackTimestamp(right) - trackTimestamp(left));
  const seen = new Set<string>();
  const unique: StreamTrack[] = [];
  for (const track of merged) {
    if (seen.has(track.id)) continue;
    seen.add(track.id);
    unique.push(track);
    if (unique.length >= limit) break;
  }
  return unique;
}

export function exploreArtistStats(artist: ExploreArtist): string {
  if ((artist.playlist_count ?? 0) > 0) {
    const playlists = artist.playlist_count ?? 0;
    const tracks = artist.track_count ?? 0;
    return `${playlists} playlist${playlists === 1 ? '' : 's'} · ${tracks} track${tracks === 1 ? '' : 's'}`;
  }
  const albums = artist.album_count ?? 0;
  const tracks = artist.track_count ?? 0;
  return `${albums} album${albums === 1 ? '' : 's'} · ${tracks} track${tracks === 1 ? '' : 's'}`;
}
