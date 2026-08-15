'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, Suspense, useEffect, useState } from 'react';
import { Search } from 'lucide-react';

import { AlbumCard, ArtistCard } from '@/components/catalog-cards';
import TrackRow from '@/components/track-row';
import { useAuth } from '@/components/auth-provider';
import { fetchLikedTracks } from '@/lib/library-api';
import {
  searchCatalog,
  type StreamAlbum,
  type StreamArtist,
  type StreamGenre,
  type StreamTrack,
} from '@/lib/streaming-api';

type Props = {
  recentTracks: StreamTrack[];
  albums: StreamAlbum[];
  artists: StreamArtist[];
  genres: StreamGenre[];
};

function ExploreBody({ recentTracks, albums, artists, genres }: Props) {
  const router = useRouter();
  const params = useSearchParams();
  const { user, loading } = useAuth();
  const initialQuery = params.get('q') ?? '';
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<StreamTrack[]>([]);
  const [liked, setLiked] = useState<StreamTrack[]>([]);

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login?next=/explore');
    }
  }, [loading, user, router]);

  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  useEffect(() => {
    const value = query.trim();
    if (!value) {
      setResults([]);
      return;
    }
    const handle = window.setTimeout(() => {
      void searchCatalog(value, 24, 0)
        .then((page) => setResults(page.items ?? []))
        .catch(() => setResults([]));
    }, 250);
    return () => window.clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    if (!user) {
      setLiked([]);
      return;
    }
    void fetchLikedTracks(12, 0)
      .then((page) => setLiked(page.items ?? []))
      .catch(() => setLiked([]));
  }, [user]);

  function onSearch(event: FormEvent) {
    event.preventDefault();
  }

  if (loading || !user) {
    return <p className="text-slate-400">Checking your session…</p>;
  }

  return (
    <div className="space-y-10">
      <section>
        <h1 className="font-display text-3xl font-semibold text-white">Explore</h1>
        <p className="mt-2 text-slate-300/75">
          Browse Camxora-published albums, artists, and genres. Search titles and styles.
        </p>
        <form onSubmit={onSearch} className="relative mt-5 max-w-xl">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search songs, artists, genres"
            className="h-12 w-full rounded-full border border-white/10 bg-white/[0.04] pl-10 pr-4 text-sm text-white outline-none focus:border-violet-400/40"
          />
        </form>
      </section>

      {results.length ? (
        <section>
          <h2 className="mb-3 font-display text-xl font-semibold text-white">Search results</h2>
          <div className="space-y-1 rounded-2xl border border-white/8 bg-white/[0.02] p-2">
            {results.map((track) => (
              <TrackRow key={track.id} track={track} queue={results} />
            ))}
          </div>
        </section>
      ) : null}

      {genres.length ? (
        <section>
          <h2 className="mb-3 font-display text-xl font-semibold text-white">Browse by genre</h2>
          <div className="flex flex-wrap gap-2">
            {genres.map((genre) => (
              <Link
                key={genre.slug}
                href={`/genres/${genre.slug}`}
                className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-slate-200 hover:bg-white/[0.07]"
              >
                {genre.genre}
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {user && liked.length ? (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-xl font-semibold text-white">Liked</h2>
            <Link href="/library" className="text-sm text-fuchsia-200/80 hover:text-white">
              Open library
            </Link>
          </div>
          <div className="space-y-1 rounded-2xl border border-white/8 bg-white/[0.02] p-2">
            {liked.map((track) => (
              <TrackRow key={track.id} track={track} queue={liked} />
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <h2 className="mb-3 font-display text-xl font-semibold text-white">Recently added</h2>
        <div className="space-y-1 rounded-2xl border border-white/8 bg-white/[0.02] p-2">
          {recentTracks.length ? (
            recentTracks.map((track) => <TrackRow key={track.id} track={track} queue={recentTracks} />)
          ) : (
            <p className="px-3 py-6 text-sm text-slate-500">No published tracks yet.</p>
          )}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold text-white">Albums</h2>
          <Link href="/albums" className="text-sm text-fuchsia-200/80 hover:text-white">
            Show all
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {albums.map((album) => (
            <AlbumCard key={album.id} album={album} />
          ))}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold text-white">Artists</h2>
          <Link href="/artists" className="text-sm text-fuchsia-200/80 hover:text-white">
            Show all
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {artists.map((artist) => (
            <ArtistCard key={artist.user_id} artist={artist} />
          ))}
        </div>
      </section>
    </div>
  );
}

export default function ExplorePageClient(props: Props) {
  return (
    <Suspense fallback={<p className="text-slate-400">Loading explore…</p>}>
      <ExploreBody {...props} />
    </Suspense>
  );
}
