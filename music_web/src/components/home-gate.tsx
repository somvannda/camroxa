'use client';

import Link from 'next/link';

import TrackRow from '@/components/track-row';
import { AlbumCard } from '@/components/catalog-cards';
import { useAuth } from '@/components/auth-provider';
import type { StreamAlbum, StreamTrack } from '@/lib/streaming-api';

export default function HomeGate({
  tracks,
  albums,
}: {
  tracks: StreamTrack[];
  albums: StreamAlbum[];
}) {
  const { user, loading } = useAuth();

  if (loading || !user) {
    return (
      <div>
        <section className="mx-auto max-w-5xl px-4 py-16 text-center md:py-24">
          <p className="text-xs uppercase tracking-[0.24em] text-fuchsia-200/70">Camxora Music</p>
          <h1 className="mt-4 font-display text-4xl font-semibold text-white md:text-6xl">
            Make any song you can imagine
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-300/75">
            Start with a simple prompt or write lyrics and styles. Create two versions, play them,
            and download MP3s — with Camxora.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/register?next=/create"
              className="inline-flex h-12 items-center rounded-full bg-white px-6 text-sm font-medium text-slate-950"
            >
              Join for free
            </Link>
            <Link
              href="/create"
              className="inline-flex h-12 items-center rounded-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-6 text-sm font-medium text-white"
            >
              Create
            </Link>
          </div>
        </section>
        <section className="mx-auto max-w-5xl px-4 pb-16">
          <h2 className="font-display text-2xl font-semibold text-white">Featured from the catalog</h2>
          <div className="mt-4 space-y-1 rounded-2xl border border-white/8 bg-white/[0.02] p-2">
            {tracks.length ? (
              tracks.slice(0, 8).map((track) => <TrackRow key={track.id} track={track} queue={tracks} />)
            ) : (
              <p className="px-3 py-6 text-sm text-slate-500">New music will appear here.</p>
            )}
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <section className="rounded-3xl border border-white/8 bg-gradient-to-br from-violet-600/20 via-purple-900/10 to-transparent p-8">
        <p className="text-xs uppercase tracking-[0.2em] text-fuchsia-100/70">Home</p>
        <h1 className="mt-2 font-display text-4xl font-semibold text-white">
          Welcome back, {user.display_name}
        </h1>
        <p className="mt-3 max-w-xl text-slate-300/75">
          Create a new song or keep exploring published Camxora music.
        </p>
        <Link
          href="/create"
          className="mt-6 inline-flex h-11 items-center rounded-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-5 text-sm font-medium text-white"
        >
          Create a song
        </Link>
      </section>
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold text-white">Recently added</h2>
          <Link href="/explore" className="text-sm text-fuchsia-200/80 hover:text-white">
            Explore
          </Link>
        </div>
        <div className="space-y-1 rounded-2xl border border-white/8 bg-white/[0.02] p-2">
          {tracks.length ? (
            tracks.map((track) => <TrackRow key={track.id} track={track} queue={tracks} />)
          ) : (
            <p className="px-3 py-6 text-sm text-slate-500">No published tracks yet.</p>
          )}
        </div>
      </section>
      <section>
        <h2 className="mb-4 font-display text-xl font-semibold text-white">Albums</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {albums.map((album) => (
            <AlbumCard key={album.id} album={album} />
          ))}
        </div>
      </section>
    </div>
  );
}
