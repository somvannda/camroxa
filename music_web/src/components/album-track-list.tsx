'use client';

import TrackRow from '@/components/track-row';
import { type StreamTrack } from '@/lib/streaming-api';
import { useMemo, type ReactNode } from 'react';

export default function AlbumTrackList({
  tracks,
  renderTrailing,
  empty,
}: {
  tracks: StreamTrack[];
  renderTrailing?: (track: StreamTrack) => ReactNode;
  empty?: ReactNode;
}) {
  const showPlays = useMemo(
    () => tracks.some((track) => (track.play_count ?? 0) > 0),
    [tracks],
  );
  const hasTrailing = Boolean(renderTrailing);

  const headerClass = showPlays
    ? hasTrailing
      ? 'grid-cols-[2.25rem_minmax(0,1fr)_4.5rem_2.5rem_4.5rem_2rem]'
      : 'grid-cols-[2.25rem_minmax(0,1fr)_4.5rem_2.5rem_4.5rem]'
    : hasTrailing
      ? 'grid-cols-[2.25rem_minmax(0,1fr)_2.5rem_4.5rem_2rem]'
      : 'grid-cols-[2.25rem_minmax(0,1fr)_2.5rem_4.5rem]';

  return (
    <div className="space-y-2">
      <div
        className={`hidden ${headerClass} gap-3 border-b border-white/8 px-3 pb-2 text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500 sm:grid`}
      >
        <span>#</span>
        <span>Title</span>
        {showPlays ? <span className="text-right">Plays</span> : null}
        <span className="sr-only">Like</span>
        <span className="text-right">Time</span>
        {hasTrailing ? <span className="sr-only">More</span> : null}
      </div>

      <div className="space-y-0.5">
        {tracks.length ? (
          tracks.map((track, index) => (
            <TrackRow
              key={track.id}
              track={track}
              queue={tracks}
              index={index + 1}
              variant="album"
              showPlays={showPlays}
              trailing={renderTrailing?.(track)}
            />
          ))
        ) : (
          empty ?? null
        )}
      </div>
    </div>
  );
}
