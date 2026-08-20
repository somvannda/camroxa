'use client';

import { Pause, Play, SkipBack, SkipForward, Volume2, VolumeX } from 'lucide-react';

import { LikeButton } from '@/components/likes-provider';
import { usePlayer } from '@/components/player-provider';
import { formatDuration, formatGenreLabels } from '@/lib/streaming-api';

function formatClock(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  const total = Math.floor(seconds);
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

export default function PlayerBar() {
  const {
    current,
    playing,
    currentTime,
    duration,
    volume,
    muted,
    queue,
    queueIndex,
    toggle,
    next,
    previous,
    seek,
    setVolume,
    toggleMute,
  } = usePlayer();

  const progressMax = duration > 0 ? duration : current?.duration_seconds ?? 0;
  const canSeek = Boolean(current) && progressMax > 0;
  const canPrev = Boolean(current);
  const canNext = queueIndex >= 0 && queueIndex < queue.length - 1;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-white/8 bg-[rgba(5,8,18,0.94)] px-4 py-3 backdrop-blur-xl md:left-72 md:px-6">
      <div className="mx-auto grid max-w-[1600px] grid-cols-1 items-center gap-3 md:grid-cols-[1.2fr_1.4fr_1fr] md:gap-4">
        <div className="flex min-w-0 items-center justify-center gap-3 md:justify-start">
          {current?.cover_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={current.cover_url} alt="" className="h-12 w-12 rounded-lg object-cover md:h-14 md:w-14" />
          ) : (
            <div className="h-12 w-12 rounded-lg bg-white/[0.06] md:h-14 md:w-14" />
          )}
          <div className="min-w-0 max-w-[70%] text-center md:max-w-none md:text-left">
            <p className="truncate font-medium text-white">
              {current?.title ?? 'Select a track to play'}
            </p>
            <p className="truncate text-sm text-slate-400">
              {current
                ? `${current.artist_name ?? 'Camxora Artist'} · ${current.album_name ?? 'Album'}${
                    formatGenreLabels(current) ? ` · ${formatGenreLabels(current)}` : ''
                  }`
                : 'Browse freely — pick a track or use Play on an album.'}
            </p>
          </div>
          {current ? <LikeButton trackId={current.id} className="ml-1 shrink-0" /> : null}
        </div>

        <div className="flex flex-col items-center gap-2">
          <div className="flex items-center justify-center gap-2">
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-400 transition hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
              aria-label="Previous"
              disabled={!canPrev}
              onClick={previous}
            >
              <SkipBack className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={toggle}
              disabled={!current}
              className="flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-[0_12px_28px_rgba(118,77,255,0.35)] disabled:cursor-not-allowed disabled:opacity-40"
              aria-label={playing ? 'Pause' : 'Play'}
            >
              {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
            </button>
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-400 transition hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
              aria-label="Next"
              disabled={!canNext}
              onClick={next}
            >
              <SkipForward className="h-4 w-4" />
            </button>
          </div>

          <div className="flex w-full max-w-xl items-center gap-2">
            <span className="w-10 shrink-0 text-right text-[11px] tabular-nums text-slate-500">
              {formatClock(currentTime)}
            </span>
            <input
              type="range"
              min={0}
              max={progressMax || 0}
              step={0.1}
              value={Math.min(currentTime, progressMax || 0)}
              disabled={!canSeek}
              onChange={(event) => seek(Number(event.target.value))}
              aria-label="Seek"
              className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-white/15 accent-fuchsia-400 disabled:cursor-not-allowed disabled:opacity-40"
            />
            <span className="w-10 shrink-0 text-[11px] tabular-nums text-slate-500">
              {formatClock(progressMax) || formatDuration(current?.duration_seconds) || '0:00'}
            </span>
          </div>
        </div>

        <div className="hidden items-center justify-end gap-2 md:flex">
          <button
            type="button"
            onClick={toggleMute}
            disabled={!current}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full text-slate-400 transition hover:text-white disabled:opacity-30"
            aria-label={muted || volume === 0 ? 'Unmute' : 'Mute'}
          >
            {muted || volume === 0 ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={muted ? 0 : volume}
            disabled={!current}
            onChange={(event) => setVolume(Number(event.target.value))}
            aria-label="Volume"
            className="h-1.5 w-28 cursor-pointer appearance-none rounded-full bg-white/15 accent-fuchsia-400 disabled:cursor-not-allowed disabled:opacity-40"
          />
        </div>
      </div>
    </div>
  );
}
