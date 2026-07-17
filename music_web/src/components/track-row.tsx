'use client';

import { Play } from 'lucide-react';
import { usePlayer } from '@/components/player-provider';
import { formatDuration, type StreamTrack } from '@/lib/streaming-api';

export default function TrackRow({ track }: { track: StreamTrack }) {
  const { playTrack } = usePlayer();
  const duration = formatDuration(track.duration_seconds);

  return (
    <button
      type="button"
      onClick={() => void playTrack(track)}
      className="group flex w-full items-center gap-4 rounded-xl px-3 py-3 text-left hover:bg-white/5"
    >
      {track.cover_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={track.cover_url} alt="" className="h-12 w-12 rounded-lg object-cover" />
      ) : (
        <div className="h-12 w-12 rounded-lg bg-[hsl(var(--secondary))]" />
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{track.title}</p>
        <p className="truncate text-sm text-[hsl(var(--muted-foreground))]">
          {track.artist_name ?? 'Camxora Artist'} · {track.album_name ?? 'Album'}
          {track.genre ? ` · ${track.genre}` : ''}
          {track.variant ? ` · ${track.variant.toUpperCase()}` : ''}
        </p>
      </div>
      {duration ? (
        <span className="text-sm tabular-nums text-[hsl(var(--muted-foreground))]">{duration}</span>
      ) : null}
      <Play className="h-4 w-4 opacity-0 transition group-hover:opacity-100" />
    </button>
  );
}
