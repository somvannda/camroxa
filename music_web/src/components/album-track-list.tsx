'use client';

import TrackRow from '@/components/track-row';
import { formatDuration, formatPlayCount, type StreamTrack } from '@/lib/streaming-api';
import { useMemo } from 'react';

export default function AlbumTrackList({ tracks }: { tracks: StreamTrack[] }) {
  const totalDuration = useMemo(() => {
    const seconds = tracks.reduce((sum, track) => sum + (track.duration_seconds ?? 0), 0);
    return seconds > 0 ? formatDuration(seconds) : null;
  }, [tracks]);

  const totalPlays = useMemo(
    () => tracks.reduce((sum, track) => sum + (track.play_count ?? 0), 0),
    [tracks],
  );

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-400">
        {tracks.length} song{tracks.length === 1 ? '' : 's'}
        {totalDuration ? ` · ${totalDuration}` : ''}
        {` · ${formatPlayCount(totalPlays)} plays`}
      </p>

      <div className="hidden grid-cols-[2.25rem_minmax(0,1fr)_5rem_2rem_4rem] gap-3 px-3 text-xs uppercase tracking-wide text-slate-500 sm:grid">
        <span>#</span>
        <span>Title</span>
        <span className="text-right">Plays</span>
        <span />
        <span className="text-right">Time</span>
      </div>

      <div className="space-y-0.5 border-t border-white/8 pt-2">
        {tracks.map((track, index) => (
          <TrackRow
            key={track.id}
            track={track}
            queue={tracks}
            index={index + 1}
            variant="album"
          />
        ))}
      </div>
    </div>
  );
}
