import ArtistsBrowser from '@/components/artists-browser';
import { mergeExploreArtists } from '@/lib/explore-api';
import { listPublicArtists } from '@/lib/playlist-api';
import { listArtists } from '@/lib/streaming-api';

export default async function ArtistsPage() {
  let streamingItems: Awaited<ReturnType<typeof listArtists>>['items'] = [];
  let webMusicItems: Awaited<ReturnType<typeof listPublicArtists>>['items'] = [];
  let streamingTotal = 0;
  let webMusicTotal = 0;

  try {
    const page = await listArtists(48, 0);
    streamingItems = page.items;
    streamingTotal = page.total;
  } catch {
    streamingItems = [];
    streamingTotal = 0;
  }
  try {
    const page = await listPublicArtists(48, 0);
    webMusicItems = page.items;
    webMusicTotal = page.total;
  } catch {
    webMusicItems = [];
    webMusicTotal = 0;
  }

  const items = mergeExploreArtists(streamingItems, webMusicItems);
  const total = Math.max(streamingTotal, webMusicTotal, items.length);

  return <ArtistsBrowser initialItems={items} total={total} />;
}
