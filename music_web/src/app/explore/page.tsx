import ExplorePageClient from '@/components/explore-page-client';
import { getGenres, getStreamingHome, listAlbums, listArtists } from '@/lib/streaming-api';

export default async function ExplorePage() {
  let recentTracks: Awaited<ReturnType<typeof getStreamingHome>>['recent_tracks'] = [];
  let albums: Awaited<ReturnType<typeof listAlbums>>['items'] = [];
  let artists: Awaited<ReturnType<typeof listArtists>>['items'] = [];
  let genres: Awaited<ReturnType<typeof getGenres>>['items'] = [];
  try {
    const home = await getStreamingHome();
    recentTracks = home.recent_tracks;
  } catch {
    recentTracks = [];
  }
  try {
    albums = (await listAlbums(8, 0)).items;
  } catch {
    albums = [];
  }
  try {
    artists = (await listArtists(8, 0)).items;
  } catch {
    artists = [];
  }
  try {
    genres = (await getGenres()).items;
  } catch {
    genres = [];
  }

  return (
    <ExplorePageClient
      recentTracks={recentTracks}
      albums={albums}
      artists={artists}
      genres={genres}
    />
  );
}
