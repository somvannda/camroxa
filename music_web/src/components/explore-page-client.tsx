'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, Suspense, useEffect, useRef, useState } from 'react';
import { Search } from 'lucide-react';

import { ArtistCard, PlaylistCard } from '@/components/catalog-cards';
import TrackRow from '@/components/track-row';
import { useAuth } from '@/components/auth-provider';
import { fetchLikedTracks } from '@/lib/library-api';
import type { ExploreArtist } from '@/lib/explore-api';
import type { WebMusicPublicPlaylist } from '@/lib/playlist-api';
import {
  searchCatalog,
  type StreamGenre,
  type StreamTrack,
} from '@/lib/streaming-api';

type Props = {
  recentTracks: StreamTrack[];
  publicPlaylists: WebMusicPublicPlaylist[];
  artists: ExploreArtist[];
  genres: StreamGenre[];
};

function ExploreBody({ recentTracks, publicPlaylists, artists, genres }: Props) {
  const router = useRouter();
  const params = useSearchParams();
  const { user, loading } = useAuth();
  const initialQuery = params.get('q') ?? '';
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<StreamTrack[]>([]);
  const [liked, setLiked] = useState<StreamTrack[]>([]);
  // Guards against an older debounced search resolving after a newer one.
  const searchSeq = useRef(0);

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
    const seq = ++searchSeq.current;
    const handle = window.setTimeout(() => {
      void searchCatalog(value, 24, 0)
        .then((page) => {
          if (seq === searchSeq.current) setResults(page.items ?? []);
        })
        .catch(() => {
          // Keep the previous results on a transient error instead of blanking.
        });
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
      .catch(() => {
        // Keep the previous list on a transient error instead of blanking.
      });
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
          Discover public playlists and published music from Camxora creators. Tracks appear here when
          added to a public playlist or published to the streaming catalog.
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
              <TrackRow key={track.id} track={track} queue={results} showGenre={false} />
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold text-white">Recent public playlists</h2>
          <Link href="/playlists" className="text-sm text-fuchsia-200/80 hover:text-white">
            Your playlists
          </Link>
        </div>
        {publicPlaylists.length ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {publicPlaylists.map((playlist) => (
              <PlaylistCard key={playlist.id} playlist={playlist} />
            ))}
          </div>
        ) : (
          <p className="rounded-2xl border border-white/8 bg-white/[0.02] px-4 py-8 text-sm text-slate-500">
            No public playlists yet. Set a playlist to public from your library to appear here.
          </p>
        )}
      </section>

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
              <TrackRow key={track.id} track={track} queue={liked} showGenre={false} />
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <h2 className="mb-3 font-display text-xl font-semibold text-white">Recently added</h2>
        <div className="space-y-1 rounded-2xl border border-white/8 bg-white/[0.02] p-2">
          {recentTracks.length ? (
            recentTracks.map((track) => (
              <TrackRow key={track.id} track={track} queue={recentTracks} showGenre={false} />
            ))
          ) : (
            <p className="px-3 py-6 text-sm text-slate-500">
              No recent tracks yet. Publish a playlist as public and add your songs, or publish to the
              streaming catalog.
            </p>
          )}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold text-white">Artists</h2>
          <Link href="/artists" className="text-sm text-fuchsia-200/80 hover:text-white">
            Show all
          </Link>
        </div>
        {artists.length ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {artists.map((artist) => (
              <ArtistCard key={artist.user_id} artist={artist} />
            ))}
          </div>
        ) : (
          <p className="rounded-2xl border border-white/8 bg-white/[0.02] px-4 py-8 text-sm text-slate-500">
            No creators yet. Published streaming artists and users with public playlists appear here.
          </p>
        )}
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
