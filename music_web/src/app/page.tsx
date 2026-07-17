import Link from 'next/link';

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
        <h1 className="text-3xl font-semibold">Good evening</h1>
        <p className="mt-2 text-[hsl(var(--muted-foreground))]">
          Discover AI-generated music published by Camxora creators.
        </p>
      </section>

      {genres.length ? (
        <section>
          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">Browse by genre</h2>
            <Link href="/genres" className="text-sm text-[hsl(var(--primary))] hover:underline">
              View all
            </Link>
          </div>
          <div className="flex flex-wrap gap-2">
            {genres.map((genre) => (
              <Link
                key={genre.slug}
                href={`/genres/${genre.slug}`}
                className="rounded-full border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-4 py-2 text-sm transition hover:bg-white/5"
              >
                {genre.genre}
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <h2 className="mb-4 text-xl font-semibold">Recently added</h2>
        <div className="space-y-1">
          {home.recent_tracks.length ? (
            home.recent_tracks.map((track) => <TrackRow key={track.id} track={track} />)
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              No published tracks yet. Complete a batch and configure Backblaze in Music Portal.
            </p>
          )}
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-xl font-semibold">Albums</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {home.albums.map((album) => (
            <a
              key={album.id}
              href={`/albums/${album.id}`}
              className="rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4 transition hover:bg-white/5"
            >
              {album.cover_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={album.cover_url}
                  alt=""
                  className="mb-4 aspect-square w-full rounded-xl object-cover"
                />
              ) : (
                <div className="mb-4 aspect-square w-full rounded-xl bg-[hsl(var(--secondary))]" />
              )}
              <p className="font-medium">{album.album_name}</p>
              <p className="text-sm text-[hsl(var(--muted-foreground))]">
                {album.artist_name ?? 'Camxora Artist'} · {album.track_count ?? 0} tracks
              </p>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
