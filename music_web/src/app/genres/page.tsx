import Link from 'next/link';

import { getGenres } from '@/lib/streaming-api';

export default async function GenresPage() {
  let genres: Awaited<ReturnType<typeof getGenres>>['items'] = [];
  try {
    const response = await getGenres();
    genres = response.items;
  } catch {
    genres = [];
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Genres</h1>
        <p className="mt-2 text-[hsl(var(--muted-foreground))]">
          Browse published albums and tracks by genre.
        </p>
      </div>

      {genres.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {genres.map((genre) => (
            <Link
              key={genre.slug}
              href={`/genres/${genre.slug}`}
              className="rounded-2xl border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 transition hover:bg-white/5"
            >
              <p className="text-lg font-medium">{genre.genre}</p>
              <p className="mt-1 text-sm text-[hsl(var(--muted-foreground))]">
                {genre.album_count} albums · {genre.track_count} tracks
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <p className="text-sm text-[hsl(var(--muted-foreground))]">
          No genres published yet. Upload streaming tracks with genre metadata to populate this page.
        </p>
      )}
    </div>
  );
}
