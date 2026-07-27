'use client';

import { Pause, Play } from 'lucide-react';

import PlayingEqualizer from '@/components/playing-equalizer';
import { LikeButton } from '@/components/likes-provider';
import { usePlayer } from '@/components/player-provider';
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
}: {
  track: StreamTrack;
  queue?: StreamTrack[];
  index?: number;
  variant?: 'default' | 'album';
}) {
  const { current, playing, playTrack, toggle } = usePlayer();
  const duration = formatDuration(track.duration_seconds);
  const genreLabel = formatGenreLabels(track);
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
      <button
        type="button"
        onClick={onPlay}
        className={`group grid w-full grid-cols-[2.25rem_1fr_auto_auto] items-center gap-3 rounded-lg px-3 py-2.5 text-left transition hover:bg-white/5 sm:grid-cols-[2.25rem_minmax(0,1fr)_5rem_2rem_4rem] ${
          isCurrent ? 'track-row-playing' : ''
        }`}
      >
        <span className="relative flex h-8 w-8 items-center justify-center">
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
        <div className="min-w-0">
          <p
            className={`truncate font-medium ${
              isCurrent ? 'text-fuchsia-200' : 'text-white'
            }`}
          >
            {track.title}
          </p>
          <p className={`truncate text-sm ${isCurrent ? 'text-fuchsia-100/70' : 'text-slate-400'}`}>
            {track.artist_name ?? 'Camxora Artist'}
          </p>
        </div>
        <span
          className={`hidden text-right text-sm tabular-nums sm:block ${
            isCurrent ? 'text-fuchsia-200/70' : 'text-slate-500'
          }`}
        >
          {plays}
        </span>
        <LikeButton trackId={track.id} size="sm" className="justify-self-center" />
        <span
          className={`text-right text-sm tabular-nums ${
            isCurrent ? 'text-fuchsia-200/80' : 'text-slate-400'
          }`}
        >
          {duration || '—'}
        </span>
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onPlay}
      className={`group flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition hover:bg-white/5 sm:gap-4 ${
        isCurrent ? 'track-row-playing' : ''
      }`}
    >
      <span className="relative shrink-0">
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
      <div className="min-w-0 flex-1">
        <p className={`truncate font-medium ${isCurrent ? 'text-fuchsia-200' : ''}`}>
          {track.title}
        </p>
        <p className="truncate text-sm text-[hsl(var(--muted-foreground))]">
          {track.artist_name ?? 'Camxora Artist'} · {track.album_name ?? 'Album'}
          {genreLabel ? ` · ${genreLabel}` : ''}
        </p>
      </div>
      <LikeButton trackId={track.id} size="sm" />
      <span className="hidden text-sm tabular-nums text-[hsl(var(--muted-foreground))] sm:inline">
        {plays} plays
      </span>
      {duration ? (
        <span className="text-sm tabular-nums text-[hsl(var(--muted-foreground))]">{duration}</span>
      ) : null}
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
  );
}
