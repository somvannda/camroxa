import Link from 'next/link';

import { AlbumCard } from '@/components/catalog-cards';
import TrackRow from '@/components/track-row';
import { getGenres, getStreamingHome } from '@/lib/streaming-api';

const emptyHome = { recent_tracks: [], albums: [] } as Awaited<
  ReturnType<typeof getStreamingHome>
>;

export default async function HomePage() {
  let home: Awaited<ReturnType<typeof getStreamingHome>> = emptyHome;
  let genres: Awaited<ReturnType<typeof getGenres>>['items'] = [];
  try {
    home = await getStreamingHome();
  } catch {
    home = emptyHome;
  }
  try {
    const response = await getGenres();
    genres = response.items.slice(0, 8);
  } catch {
    genres = [];
  }

  return (
    <div className="space-y-10">
      <section>
        <h1 className="font-display text-3xl font-semibold text-white md:text-4xl">Good evening</h1>
        <p className="mt-2 max-w-2xl text-slate-300/75">
          Discover AI-generated music published by Camxora creators. Browse freely — sign in to
          listen, save, and build playlists.
        </p>
      </section>

      {genres.length ? (
        <section>
          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 className="font-display text-xl font-semibold text-white">Browse by genre</h2>
            <Link href="/genres" className="text-sm text-fuchsia-200/80 hover:text-white">
              View all
            </Link>
          </div>
          <div className="flex flex-wrap gap-2">
            {genres.map((genre) => (
              <Link
                key={genre.slug}
                href={`/genres/${genre.slug}`}
                className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-slate-200 transition hover:bg-white/[0.07]"
              >
                {genre.genre}
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="font-display text-xl font-semibold text-white">Recently added</h2>
        </div>
        <div className="space-y-1 rounded-2xl border border-white/8 bg-white/[0.02] p-2">
          {home.recent_tracks.length ? (
            home.recent_tracks.map((track) => <TrackRow key={track.id} track={track} />)
          ) : (
            <p className="px-3 py-6 text-sm text-slate-500">
              No published tracks yet. Complete a batch and configure streaming storage.
            </p>
          )}
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="font-display text-xl font-semibold text-white">Albums</h2>
          <Link href="/albums" className="text-sm text-fuchsia-200/80 hover:text-white">
            Show all
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {home.albums.map((album) => (
            <AlbumCard key={album.id} album={album} />
          ))}
        </div>
      </section>
    </div>
  );
}
