'use client';

import { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

import TrackRow from '@/components/track-row';
import { formatDuration, type StreamTrack } from '@/lib/streaming-api';

type AlbumTrack = StreamTrack & { lyrics?: string | null };

export default function AlbumTrackList({ tracks }: { tracks: AlbumTrack[] }) {
  const [expandedTrackId, setExpandedTrackId] = useState<string | null>(null);

  const totalDuration = useMemo(() => {
    const seconds = tracks.reduce((sum, track) => sum + (track.duration_seconds ?? 0), 0);
    return seconds > 0 ? formatDuration(seconds) : null;
  }, [tracks]);

  return (
    <div className="space-y-4">
      {totalDuration ? (
        <p className="text-sm text-[hsl(var(--muted-foreground))]">
          {tracks.length} tracks · {totalDuration} total
        </p>
      ) : (
        <p className="text-sm text-[hsl(var(--muted-foreground))]">{tracks.length} tracks</p>
      )}
      <div className="space-y-1">
        {tracks.map((track) => {
          const hasLyrics = Boolean(track.lyrics?.trim());
          const expanded = expandedTrackId === track.id;
          return (
            <div key={track.id} className="rounded-xl border border-transparent hover:border-white/5">
              <TrackRow track={track} />
              {hasLyrics ? (
                <div className="px-3 pb-3">
                  <button
                    type="button"
                    onClick={() => setExpandedTrackId(expanded ? null : track.id)}
                    className="flex items-center gap-1 text-xs text-[hsl(var(--muted-foreground))] hover:text-white"
                  >
                    {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    {expanded ? 'Hide lyrics' : 'Show lyrics'}
                  </button>
                  {expanded ? (
                    <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-white/5 p-3 text-sm text-[hsl(var(--muted-foreground))]">
                      {track.lyrics}
                    </pre>
                  ) : null}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
