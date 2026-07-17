'use client';

import { Pause, Play } from 'lucide-react';
import { usePlayer } from '@/components/player-provider';
import { formatDuration } from '@/lib/streaming-api';

export default function PlayerBar() {
  const { current, playing, toggle } = usePlayer();
  if (!current) return null;
  const duration = formatDuration(current.duration_seconds);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-[hsl(var(--border))] bg-[hsl(var(--card))]/95 px-6 py-3 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4">
        {current.cover_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={current.cover_url} alt="" className="h-14 w-14 rounded-lg object-cover" />
        ) : (
          <div className="h-14 w-14 rounded-lg bg-[hsl(var(--secondary))]" />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{current.title}</p>
          <p className="truncate text-sm text-[hsl(var(--muted-foreground))]">
            {current.artist_name ?? 'Camxora Artist'} · {current.album_name ?? 'Album'}
            {current.genre ? ` · ${current.genre}` : ''}
            {duration ? ` · ${duration}` : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={toggle}
          className="flex h-11 w-11 items-center justify-center rounded-full bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
        >
          {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
        </button>
      </div>
    </div>
  );
}
