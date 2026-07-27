import AlbumsBrowser from '@/components/albums-browser';
import { listAlbums } from '@/lib/streaming-api';

export default async function AlbumsPage() {
  let items: Awaited<ReturnType<typeof listAlbums>>['items'] = [];
  let total = 0;
  try {
    const page = await listAlbums(24, 0);
    items = page.items;
    total = page.total;
  } catch {
    items = [];
    total = 0;
  }
  return <AlbumsBrowser initialItems={items} total={total} />;
}
