import TrackRow from '@/components/track-row';
import { CoverImage } from '@/components/cover-image';
import { getGenre } from '@/lib/streaming-api';

export default async function GenreDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let genre: Awaited<ReturnType<typeof getGenre>> | null = null;
  try {
    genre = await getGenre(slug);
  } catch {
    genre = null;
  }

  if (!genre) {
    return (
      <div>
        <h1 className="text-2xl font-semibold">Genre not found</h1>
        <p className="mt-2 text-sm text-[hsl(var(--muted-foreground))]">
          This genre is not in the published catalog.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-3xl font-semibold">{genre.genre}</h1>
        <p className="mt-2 text-[hsl(var(--muted-foreground))]">
          {genre.album_count} albums · {genre.track_count} tracks
        </p>
      </section>

      <section>
        <h2 className="mb-4 text-xl font-semibold">Albums</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {genre.albums.length ? (
            genre.albums.map((album) => (
              <a
                key={album.id}
                href={`/albums/${album.id}`}
                className="rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4 transition hover:bg-white/5"
              >
                <CoverImage
                  src={album.cover_url}
                  className="mb-4 aspect-square w-full rounded-xl object-cover"
                  fallback={<div className="mb-4 aspect-square w-full rounded-xl bg-[hsl(var(--secondary))]" />}
                />
                <p className="font-medium">{album.album_name}</p>
                <p className="text-sm text-[hsl(var(--muted-foreground))]">
                  {album.artist_name ?? 'Camxora Artist'} · {album.track_count ?? 0} tracks
                </p>
              </a>
            ))
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))]">No albums in this genre yet.</p>
          )}
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-xl font-semibold">Tracks</h2>
        <div className="space-y-1">
          {genre.tracks.length ? (
            genre.tracks.map((track) => <TrackRow key={track.id} track={track} />)
          ) : (
            <p className="text-sm text-[hsl(var(--muted-foreground))]">No tracks in this genre yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}
