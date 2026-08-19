import HomeGate from '@/components/home-gate';
import { mergeExploreArtists, mergeRecentTracks } from '@/lib/explore-api';
import { listPublicArtists, listPublicRecentTracks } from '@/lib/playlist-api';
import { getStreamingHome, listArtists } from '@/lib/streaming-api';

const emptyHome = { recent_tracks: [], albums: [] } as Awaited<ReturnType<typeof getStreamingHome>>;

export default async function HomePage() {
  let home: Awaited<ReturnType<typeof getStreamingHome>> = emptyHome;
  let streamingRecent: Awaited<ReturnType<typeof getStreamingHome>>['recent_tracks'] = [];
  let publicRecent: Awaited<ReturnType<typeof listPublicRecentTracks>>['items'] = [];
  let streamingArtists: Awaited<ReturnType<typeof listArtists>>['items'] = [];
  let webMusicArtists: Awaited<ReturnType<typeof listPublicArtists>>['items'] = [];

  try {
    home = await getStreamingHome();
    streamingRecent = home.recent_tracks;
  } catch {
    home = emptyHome;
    streamingRecent = [];
  }
  try {
    publicRecent = (await listPublicRecentTracks(12, 0)).items;
  } catch {
    publicRecent = [];
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

  const tracks = mergeRecentTracks(streamingRecent, publicRecent, 12);
  const artists = mergeExploreArtists(streamingArtists, webMusicArtists).slice(0, 8);

  return <HomeGate tracks={tracks} albums={home.albums} artists={artists} />;
}
