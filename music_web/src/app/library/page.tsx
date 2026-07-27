'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Heart, ListMusic } from 'lucide-react';

import { useAuth } from '@/components/auth-provider';
import { useLikes } from '@/components/likes-provider';
import TrackRow from '@/components/track-row';
import { fetchLikedTracks } from '@/lib/library-api';
import type { StreamTrack } from '@/lib/streaming-api';

export default function LibraryPage() {
  const { user, loading } = useAuth();
  const { likedIds } = useLikes();
  const [tracks, setTracks] = useState<StreamTrack[]>([]);
  const [total, setTotal] = useState(0);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState(false);

  const loadLikes = useCallback(async () => {
    setListLoading(true);
    setListError(false);
    try {
      const page = await fetchLikedTracks(100, 0);
      setTracks(page.items ?? []);
      setTotal(page.total ?? 0);
    } catch {
      setListError(true);
      setTracks([]);
      setTotal(0);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user) {
      setTracks([]);
      setTotal(0);
      return;
    }
    void loadLikes();
  }, [user, loadLikes]);

  if (loading) {
    return <p className="text-slate-400">Loading your library…</p>;
  }

  if (!user) {
    return (
      <div className="rounded-3xl border border-white/8 bg-[rgba(8,10,20,0.55)] p-10">
        <h1 className="font-display text-3xl font-semibold text-white">Your Library</h1>
        <p className="mt-3 max-w-lg text-slate-300/70">
          Sign in on Music Streaming to save tracks and build playlists. You won&apos;t be sent to
          the studio portal dashboard.
        </p>
        <div className="mt-6 flex gap-3">
          <Link
            href="/login?next=/library"
            className="inline-flex h-11 items-center rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white"
          >
            Sign in
          </Link>
          <Link
            href="/register?next=/library"
            className="inline-flex h-11 items-center rounded-xl border border-white/10 px-5 text-sm font-medium text-slate-100"
          >
            Sign up
          </Link>
        </div>
      </div>
    );
  }

  const visibleTracks = tracks.filter((track) => likedIds.has(track.id));
  const displayTotal = likedIds.size || total;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-4xl font-semibold text-white">Your Library</h1>
        <p className="mt-2 text-slate-300/70">
          Hi {user.display_name} — liked songs sync on Music Streaming.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
          <ListMusic className="h-5 w-5 text-fuchsia-200/80" />
          <h2 className="mt-3 font-display text-lg font-semibold text-white">Playlists</h2>
          <p className="mt-2 text-sm text-slate-300/65">
            Custom playlists are next. For now, save tracks to Liked Songs with the heart.
          </p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-violet-600/20 via-fuchsia-600/10 to-transparent p-6">
          <Heart className="h-5 w-5 text-fuchsia-300" />
          <h2 className="mt-3 font-display text-lg font-semibold text-white">Liked Songs</h2>
          <p className="mt-2 text-sm text-slate-300/75">
            {displayTotal} track{displayTotal === 1 ? '' : 's'} saved
          </p>
        </div>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold text-white">Liked Songs</h2>
          <button
            type="button"
            onClick={() => void loadLikes()}
            className="text-xs text-fuchsia-200/70 hover:text-white"
          >
            Refresh
          </button>
        </div>
        {listLoading ? <p className="text-sm text-slate-400">Loading liked tracks…</p> : null}
        {listError ? (
          <p className="text-sm text-red-300">Could not load likes. Try refresh.</p>
        ) : null}
        {!listLoading && !listError && visibleTracks.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center">
            <p className="text-slate-300">No liked songs yet.</p>
            <p className="mt-2 text-sm text-slate-500">
              Tap the heart on the player or a track to save it here.
            </p>
            <Link
              href="/albums"
              className="mt-4 inline-flex text-sm text-fuchsia-200/80 hover:text-white"
            >
              Browse albums →
            </Link>
          </div>
        ) : null}
        <div className="space-y-1">
          {visibleTracks.map((track) => (
            <TrackRow key={track.id} track={track} queue={visibleTracks} />
          ))}
        </div>
      </section>
    </div>
  );
}
