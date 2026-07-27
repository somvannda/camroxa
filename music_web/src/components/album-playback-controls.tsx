'use client';

import { Pause, Play, Shuffle } from 'lucide-react';

import { usePlayer } from '@/components/player-provider';
import type { StreamTrack } from '@/lib/streaming-api';

export default function AlbumPlaybackControls({ tracks }: { tracks: StreamTrack[] }) {
  const { current, playing, playQueue, playShuffled, toggle } = usePlayer();

  if (!tracks.length) return null;

  const currentInAlbum = Boolean(current && tracks.some((track) => track.id === current.id));
  const showPause = currentInAlbum && playing;

  return (
    <div className="mt-6 flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={() => {
          if (currentInAlbum) {
            toggle();
            return;
          }
          void playQueue(tracks, 0);
        }}
        className="inline-flex h-12 items-center gap-2 rounded-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-6 text-sm font-semibold text-white shadow-[0_12px_28px_rgba(118,77,255,0.35)] transition hover:brightness-110"
      >
        {showPause ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
        {showPause ? 'Pause' : 'Play'}
      </button>
      <button
        type="button"
        onClick={() => void playShuffled(tracks)}
        className="inline-flex h-12 items-center gap-2 rounded-full border border-white/15 bg-white/5 px-5 text-sm font-medium text-white transition hover:bg-white/10"
      >
        <Shuffle className="h-4 w-4" />
        Shuffle
      </button>
    </div>
  );
}
