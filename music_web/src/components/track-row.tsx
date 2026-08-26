'use client';

import { Pause, Play } from 'lucide-react';
import type { ReactNode } from 'react';

import PlayingEqualizer from '@/components/playing-equalizer';
import { LikeButton } from '@/components/likes-provider';
import { usePlayer } from '@/components/player-provider';
import { khmerTextClass } from '@/lib/khmer-text';
import {
  formatDuration,
  formatGenreLabels,
  formatPlayCount,
  type StreamTrack,
} from '@/lib/streaming-api';

export default function TrackRow({
  track,
  queue,
  index,
  variant = 'default',
  showGenre = true,
  showPlays = true,
  trailing,
}: {
  track: StreamTrack;
  queue?: StreamTrack[];
  index?: number;
  variant?: 'default' | 'album';
  showGenre?: boolean;
  showPlays?: boolean;
  trailing?: ReactNode;
}) {
  const { current, playing, playTrack, toggle } = usePlayer();
  const duration = formatDuration(track.duration_seconds);
  const genreLabel = showGenre ? formatGenreLabels(track) : '';
  const plays = formatPlayCount(track.play_count);
  const isCurrent = current?.id === track.id;
  const isPlaying = isCurrent && playing;

  const onPlay = () => {
    if (isCurrent) {
      toggle();
      return;
    }
    void playTrack(track, queue);
  };

  if (variant === 'album') {
    return (
      <div
        className={`group relative grid w-full items-center gap-3 rounded-lg px-3 py-2.5 transition ${
          showPlays
            ? trailing
              ? 'grid-cols-[2.25rem_minmax(0,1fr)_2.5rem_4.5rem_2rem] sm:grid-cols-[2.25rem_minmax(0,1fr)_4.5rem_2.5rem_4.5rem_2rem]'
              : 'grid-cols-[2.25rem_minmax(0,1fr)_2.5rem_4.5rem] sm:grid-cols-[2.25rem_minmax(0,1fr)_4.5rem_2.5rem_4.5rem]'
            : trailing
              ? 'grid-cols-[2.25rem_minmax(0,1fr)_2.5rem_4.5rem_2rem]'
              : 'grid-cols-[2.25rem_minmax(0,1fr)_2.5rem_4.5rem]'
        } ${isCurrent ? 'track-row-playing' : 'hover:bg-white/[0.045]'}`}
      >
        <button
          type="button"
          onClick={onPlay}
          className="absolute inset-0 rounded-lg"
          aria-label={isPlaying ? `Pause ${track.title}` : `Play ${track.title}`}
        />
        <span className="pointer-events-none relative z-10 flex h-8 w-8 items-center justify-center">
          {isCurrent ? (
            <>
              <span className="group-hover:opacity-0">
                <PlayingEqualizer playing={isPlaying} />
              </span>
              <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100">
                {isPlaying ? (
                  <Pause className="h-4 w-4 text-fuchsia-200" />
                ) : (
                  <Play className="h-4 w-4 text-fuchsia-200" />
                )}
              </span>
            </>
          ) : (
            <>
              <span className="tabular-nums text-sm text-slate-500 group-hover:opacity-0">
                {typeof index === 'number' ? index : '·'}
              </span>
              <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100">
                <Play className="h-4 w-4 text-white" />
              </span>
            </>
          )}
        </span>
        <div className="pointer-events-none relative z-10 min-w-0">
          <p
            className={`truncate font-medium ${khmerTextClass(track.title)} ${
              isCurrent ? 'text-fuchsia-200' : 'text-white'
            }`}
          >
            {track.title}
          </p>
          <p className={`truncate text-sm ${isCurrent ? 'text-fuchsia-100/70' : 'text-slate-400'}`}>
            {track.artist_name ?? 'Camxora Artist'}
          </p>
        </div>
        {showPlays ? (
          <span
            className={`pointer-events-none relative z-10 hidden text-right text-sm tabular-nums sm:block ${
              isCurrent ? 'text-fuchsia-200/70' : 'text-slate-500'
            }`}
          >
            {plays}
          </span>
        ) : null}
        <LikeButton trackId={track.id} size="sm" className="relative z-10 justify-self-center" />
        <span
          className={`pointer-events-none relative z-10 text-right text-sm tabular-nums ${
            isCurrent ? 'text-fuchsia-200/80' : 'text-slate-400'
          }`}
        >
          {duration || '—'}
        </span>
        {trailing ? <div className="relative z-10 justify-self-end">{trailing}</div> : null}
      </div>
    );
  }

  return (
    <div
      className={`group grid w-full grid-cols-[3rem_minmax(0,1fr)_2.5rem_3rem_2.5rem] items-center gap-3 rounded-xl px-3 py-3 sm:grid-cols-[3rem_minmax(0,1fr)_2.5rem_5.5rem_3rem_2.5rem] sm:gap-4 ${
        isCurrent ? 'track-row-playing' : ''
      }`}
    >
      <button
        type="button"
        onClick={onPlay}
        className="relative shrink-0 justify-self-start"
        aria-label={isPlaying ? `Pause ${track.title}` : `Play ${track.title}`}
      >
        <span className="relative block">
          {track.cover_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={track.cover_url} alt="" className="h-12 w-12 rounded-lg object-cover" />
          ) : (
            <div className="h-12 w-12 rounded-lg bg-[hsl(var(--secondary))]" />
          )}
          {isCurrent ? (
            <span className="absolute inset-0 flex items-center justify-center rounded-lg bg-black/45">
              <PlayingEqualizer playing={isPlaying} />
            </span>
          ) : null}
        </span>
      </button>

      <button
        type="button"
        onClick={onPlay}
        className="min-w-0 text-left transition hover:opacity-90"
      >
        <p className={`truncate font-medium ${khmerTextClass(track.title)} ${isCurrent ? 'text-fuchsia-200' : ''}`}>
          {track.title}
        </p>
        <p className="truncate text-sm text-[hsl(var(--muted-foreground))]">
          {track.artist_name ?? 'Camxora Artist'}
          {track.album_name ? ` · ${track.album_name}` : ''}
          {genreLabel ? ` · ${genreLabel}` : ''}
        </p>
      </button>

      <LikeButton trackId={track.id} size="sm" className="justify-self-center" />

      <span
        className={`hidden text-right text-sm tabular-nums text-[hsl(var(--muted-foreground))] sm:block ${
          showPlays ? '' : 'invisible'
        }`}
      >
        {showPlays ? `${plays} plays` : '0 plays'}
      </span>

      <span
        className={`text-right text-sm tabular-nums ${
          isCurrent ? 'text-fuchsia-200/80' : 'text-[hsl(var(--muted-foreground))]'
        }`}
      >
        {duration || '—'}
      </span>

      <button
        type="button"
        onClick={onPlay}
        className="flex h-8 w-8 shrink-0 items-center justify-center justify-self-end"
        aria-label={isPlaying ? `Pause ${track.title}` : `Play ${track.title}`}
      >
        {isCurrent ? (
          isPlaying ? (
            <Pause className="h-4 w-4 text-fuchsia-300" />
          ) : (
            <Play className="h-4 w-4 text-fuchsia-300" />
          )
        ) : (
          <Play className="h-4 w-4 opacity-0 transition group-hover:opacity-100" />
        )}
      </button>
    </div>
  );
}
