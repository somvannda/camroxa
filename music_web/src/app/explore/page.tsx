import ExplorePageClient from '@/components/explore-page-client';
import { mergeExploreArtists, mergeRecentTracks } from '@/lib/explore-api';
import { listPublicArtists, listPublicPlaylists, listPublicRecentTracks } from '@/lib/playlist-api';
import { getGenres, getStreamingHome, listArtists } from '@/lib/streaming-api';

export default async function ExplorePage() {
  let streamingRecent: Awaited<ReturnType<typeof getStreamingHome>>['recent_tracks'] = [];
  let publicRecent: Awaited<ReturnType<typeof listPublicRecentTracks>>['items'] = [];
  let publicPlaylists: Awaited<ReturnType<typeof listPublicPlaylists>>['items'] = [];
  let streamingArtists: Awaited<ReturnType<typeof listArtists>>['items'] = [];
  let webMusicArtists: Awaited<ReturnType<typeof listPublicArtists>>['items'] = [];
  let genres: Awaited<ReturnType<typeof getGenres>>['items'] = [];

  try {
    const home = await getStreamingHome();
    streamingRecent = home.recent_tracks;
  } catch {
    streamingRecent = [];
  }
  try {
    publicRecent = (await listPublicRecentTracks(12, 0)).items;
  } catch {
    publicRecent = [];
  }
  try {
    publicPlaylists = (await listPublicPlaylists(8, 0)).items;
  } catch {
    publicPlaylists = [];
  }
  try {
    streamingArtists = (await listArtists(24, 0)).items;
  } catch {
    streamingArtists = [];
  }
  try {
    webMusicArtists = (await listPublicArtists(24, 0)).items;
  } catch {
    webMusicArtists = [];
  }
  try {
    genres = (await getGenres()).items;
  } catch {
    genres = [];
  }

  const recentTracks = mergeRecentTracks(streamingRecent, publicRecent, 12);
  const artists = mergeExploreArtists(streamingArtists, webMusicArtists).slice(0, 8);

  return (
    <ExplorePageClient
      recentTracks={recentTracks}
      publicPlaylists={publicPlaylists}
      artists={artists}
      genres={genres}
    />
  );
}
