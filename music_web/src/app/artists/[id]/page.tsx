import Link from 'next/link';

import { AlbumCard } from '@/components/catalog-cards';
import { getArtist } from '@/lib/streaming-api';

export default async function ArtistPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let artist: Awaited<ReturnType<typeof getArtist>> | null = null;
  try {
    artist = await getArtist(id);
  } catch {
    artist = null;
  }

  if (!artist) {
    return <p className="text-slate-400">Artist not found.</p>;
  }

  return (
    <div className="space-y-8">
      <section className="overflow-hidden rounded-3xl border border-white/8 bg-gradient-to-br from-violet-600/30 via-purple-900/20 to-transparent p-8 md:p-10">
        <p className="text-xs uppercase tracking-[0.2em] text-fuchsia-100/70">Artist</p>
        <h1 className="mt-3 font-display text-4xl font-semibold text-white md:text-6xl">
          {artist.artist_name ?? 'Camxora Artist'}
        </h1>
        <p className="mt-3 text-slate-300/75">
          {artist.albums.length} album{artist.albums.length === 1 ? '' : 's'} on Camxora Music
        </p>
        <Link
          href="/artists"
          className="mt-6 inline-flex text-sm text-fuchsia-200/80 hover:text-white"
        >
          ← All artists
        </Link>
      </section>

      <section>
        <h2 className="mb-4 font-display text-xl font-semibold text-white">Discography</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {artist.albums.map((album) => (
            <AlbumCard key={album.id} album={album} />
          ))}
        </div>
      </section>
    </div>
  );
}
