import ArtistsBrowser from '@/components/artists-browser';
import { listArtists } from '@/lib/streaming-api';

export default async function ArtistsPage() {
  let items: Awaited<ReturnType<typeof listArtists>>['items'] = [];
  let total = 0;
  try {
    const page = await listArtists(48, 0);
    items = page.items;
    total = page.total;
  } catch {
    items = [];
    total = 0;
  }
  return <ArtistsBrowser initialItems={items} total={total} />;
}
