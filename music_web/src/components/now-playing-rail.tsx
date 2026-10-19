'use client';

import Link from 'next/link';

import TrackRow from '@/components/track-row';
import { CoverImage } from '@/components/cover-image';
import SyncedLyrics from '@/components/synced-lyrics';
import { usePlayer } from '@/components/player-provider';
import { khmerTextClass } from '@/lib/khmer-text';
import {
  formatGenreLabels,
  formatPlayCount,
  type StreamAlbum,
  type StreamArtist,
  type StreamTrack,
} from '@/lib/streaming-api';

function DiscoverySections({
  tracks,
  albums,
  artists,
}: {
  tracks: StreamTrack[];
  albums: StreamAlbum[];
  artists: StreamArtist[];
}) {
  return (
    <>
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Trending songs</h2>
          <Link href="/search" className="text-xs text-fuchsia-200/70 hover:text-white">
            Search
          </Link>
        </div>
        <div className="space-y-1">
          {tracks.slice(0, 5).map((track) => (
            <TrackRow key={track.id} track={track} />
          ))}
          {!tracks.length ? <p className="text-xs text-slate-500">No tracks yet.</p> : null}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Popular albums</h2>
          <Link href="/albums" className="text-xs text-fuchsia-200/70 hover:text-white">
            Show all
          </Link>
        </div>
        <div className="space-y-3">
          {albums.slice(0, 4).map((album) => (
            <Link key={album.id} href={`/albums/${album.id}`} className="flex gap-3 hover:opacity-90">
              <CoverImage
                src={album.cover_url}
                className="h-12 w-12 rounded-md object-cover"
                fallback={<div className="h-12 w-12 rounded-md bg-white/[0.06]" />}
              />
              <div className="min-w-0">
                <p className="truncate text-sm text-white">{album.album_name}</p>
                <p className="truncate text-xs text-slate-400">{album.artist_name}</p>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Popular artists</h2>
          <Link href="/artists" className="text-xs text-fuchsia-200/70 hover:text-white">
            Show all
          </Link>
        </div>
        <div className="space-y-3">
          {artists.slice(0, 4).map((artist) => (
            <Link
              key={artist.user_id}
              href={`/artists/${artist.user_id}`}
              className="flex items-center gap-3 hover:opacity-90"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-violet-500/25 text-sm font-semibold text-white">
                {(artist.artist_name || 'C').slice(0, 1).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm text-white">{artist.artist_name}</p>
                <p className="truncate text-xs text-slate-400">{artist.track_count ?? 0} tracks</p>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}

function NowPlayingPanel() {
  const { current, queue, queueIndex, playing, playTrack } = usePlayer();
  if (!current) return null;

  const upcoming = queue.slice(queueIndex + 1, queueIndex + 4);
  const genreLabel = formatGenreLabels(current);
  const albumHref = current.album_id ? `/albums/${current.album_id}` : null;
  const artistHref = current.user_id ? `/artists/${current.user_id}` : null;
  const hasLyrics = Boolean(current.lyrics?.trim());

  return (
    <div className="space-y-4">
      <section className="flex gap-3">
        <CoverImage
          src={current.cover_url}
          className="h-16 w-16 shrink-0 rounded-lg object-cover shadow-lg"
          fallback={<div className="h-16 w-16 shrink-0 rounded-lg bg-white/[0.06]" />}
        />
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            {playing ? 'Now playing' : 'Paused'}
          </p>
          <p className={`mt-1 font-semibold leading-snug text-white ${khmerTextClass(current.title)}`}>
            {current.title}
          </p>
          {artistHref ? (
            <Link
              href={artistHref}
              className="mt-0.5 block truncate text-sm text-fuchsia-200/80 hover:text-white"
            >
              {current.artist_name ?? 'Camxora Artist'}
            </Link>
          ) : (
            <p className="mt-0.5 truncate text-sm text-slate-400">
              {current.artist_name ?? 'Camxora Artist'}
            </p>
          )}
          <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-slate-500">
            {albumHref ? (
              <Link href={albumHref} className="truncate hover:text-slate-300">
                {current.album_name ?? 'Album'}
              </Link>
            ) : (
              <span className="truncate">{current.album_name ?? 'Album'}</span>
            )}
            {genreLabel ? <span>· {genreLabel}</span> : null}
            <span>· {formatPlayCount(current.play_count)} plays</span>
          </div>
        </div>
      </section>

      {hasLyrics ? (
        <SyncedLyrics lyrics={current.lyrics} />
      ) : (
        <div className="rounded-xl border border-dashed border-white/10 p-4 text-sm text-slate-500">
          Lyrics will appear here when this track has them.
        </div>
      )}

      <section className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          About the artist
        </p>
        <div className="mt-3 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-violet-500/40 to-fuchsia-500/30 font-display text-base font-semibold text-white">
            {(current.artist_name || 'C').slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">
              {current.artist_name ?? 'Camxora Artist'}
            </p>
            <p className="text-xs text-slate-500">On Camxora Music</p>
          </div>
          {artistHref ? (
            <Link
              href={artistHref}
              className="shrink-0 rounded-full border border-white/15 px-3 py-1 text-[11px] font-medium text-white transition hover:bg-white/10"
            >
              View
            </Link>
          ) : null}
        </div>
      </section>

      {upcoming.length ? (
        <section>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Next up
          </p>
          <div className="space-y-1">
            {upcoming.map((track) => (
              <button
                key={track.id}
                type="button"
                onClick={() => void playTrack(track, queue)}
                className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-white/5"
              >
                <CoverImage
                  src={track.cover_url}
                  className="h-10 w-10 rounded object-cover"
                  fallback={<div className="h-10 w-10 rounded bg-white/[0.06]" />}
                />
                <div className="min-w-0">
                  <p className={`truncate text-sm text-white ${khmerTextClass(track.title)}`}>
                    {track.title}
                  </p>
                  <p className="truncate text-xs text-slate-500">{track.artist_name}</p>
                </div>
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

export function DiscoveryRail({
  tracks,
  albums,
  artists,
}: {
  tracks: StreamTrack[];
  albums: StreamAlbum[];
  artists: StreamArtist[];
}) {
  const { current } = usePlayer();

  return (
    <aside className="hidden w-[26rem] shrink-0 xl:block">
      <div
        className={`sticky top-24 max-h-[calc(100vh-8rem)] space-y-6 rounded-2xl border border-white/8 bg-[rgba(8,10,20,0.72)] p-4 backdrop-blur ${
          current ? 'overflow-hidden' : 'overflow-y-auto'
        }`}
      >
        {current ? (
          <NowPlayingPanel />
        ) : (
          <DiscoverySections tracks={tracks} albums={albums} artists={artists} />
        )}
      </div>
    </aside>
  );
}
