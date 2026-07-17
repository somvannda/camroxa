'use client';

import { createContext, useContext, useMemo, useRef, useState } from 'react';
import { getPlayUrl, type StreamTrack } from '@/lib/streaming-api';

type PlayerState = {
  current: StreamTrack | null;
  playing: boolean;
  playTrack: (track: StreamTrack) => Promise<void>;
  toggle: () => void;
};

const PlayerContext = createContext<PlayerState | null>(null);

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [current, setCurrent] = useState<StreamTrack | null>(null);
  const [playing, setPlaying] = useState(false);

  const value = useMemo<PlayerState>(
    () => ({
      current,
      playing,
      async playTrack(track) {
        const payload = await getPlayUrl(track.id);
        if (!audioRef.current) {
          audioRef.current = new Audio();
          audioRef.current.addEventListener('ended', () => setPlaying(false));
        }
        audioRef.current.src = payload.url;
        setCurrent({
          ...track,
          title: payload.title ?? track.title,
          album_name: payload.album_name ?? track.album_name,
          artist_name: payload.artist_name ?? track.artist_name,
          cover_url: payload.cover_url ?? track.cover_url,
          duration_seconds: payload.duration_seconds ?? track.duration_seconds,
          genre: payload.genre ?? track.genre,
        });
        await audioRef.current.play();
        setPlaying(true);
      },
      toggle() {
        if (!audioRef.current) return;
        if (audioRef.current.paused) {
          void audioRef.current.play();
          setPlaying(true);
        } else {
          audioRef.current.pause();
          setPlaying(false);
        }
      },
    }),
    [current, playing],
  );

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}

export function usePlayer() {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider');
  return ctx;
}
