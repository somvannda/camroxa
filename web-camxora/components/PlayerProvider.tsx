"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Track = {
  title: string;
  artist: string;
  cover: string;
  duration: number;
  elapsed?: number;
};

const defaultTracks: Track[] = [
  {
    title: "Phnom Penh Tonight",
    artist: "Sochcat AI",
    cover: "/hero.png",
    duration: 252,
    elapsed: 208,
  },
  {
    title: "Bassac Moon",
    artist: "Kanya",
    cover: "/hero.png",
    duration: 204,
  },
  {
    title: "Golden Hour",
    artist: "Malis",
    cover:
      "https://images.unsplash.com/photo-1461360228754-6e81c478b882?auto=format&fit=crop&w=600&q=80",
    duration: 182,
  },
];

type PlayerContextValue = {
  tracks: Track[];
  current: Track;
  playing: boolean;
  elapsed: number;
  liked: boolean;
  muted: boolean;
  queueOpen: boolean;
  currentIndex: number;
  playTrack: (track: Track) => void;
  loadIndex: (index: number) => void;
  togglePlay: () => void;
  seek: (seconds: number) => void;
  next: () => void;
  previous: () => void;
  toggleLike: () => void;
  toggleMute: () => void;
  toggleQueue: () => void;
};

const PlayerContext = createContext<PlayerContextValue | null>(null);

export function PlayerProvider({ children }: { children: ReactNode }) {
  const [tracks, setTracks] = useState<Track[]>(defaultTracks);
  const [current, setCurrent] = useState<Track>(defaultTracks[0]);
  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(defaultTracks[0].elapsed ?? 0);
  const [liked, setLiked] = useState(false);
  const [muted, setMuted] = useState(false);
  const [queueOpen, setQueueOpen] = useState(false);

  const currentIndex = tracks.findIndex(
    (track) => track.title === current.title && track.artist === current.artist
  );

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setElapsed((value) => {
        if (value + 1 >= current.duration) {
          setPlaying(false);
          return current.duration;
        }
        return value + 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [playing, current.duration]);

  const playTrack = (track: Track) => {
    setTracks((items) =>
      items.some(
        (item) => item.title === track.title && item.artist === track.artist
      )
        ? items
        : [...items, track]
    );
    setCurrent(track);
    setElapsed(track.elapsed ?? 0);
    setPlaying(true);
    setQueueOpen(false);
  };

  const loadIndex = (index: number) => {
    const track = tracks[index];
    if (!track) return;
    setCurrent(track);
    setElapsed(0);
    setPlaying(true);
    setQueueOpen(false);
  };

  const next = () => {
    if (!tracks.length) return;
    const base = currentIndex === -1 ? 0 : currentIndex;
    loadIndex((base + 1) % tracks.length);
  };

  const previous = () => {
    if (!tracks.length) return;
    const base = currentIndex === -1 ? 0 : currentIndex;
    loadIndex((base - 1 + tracks.length) % tracks.length);
  };

  const value: PlayerContextValue = {
    tracks,
    current,
    playing,
    elapsed,
    liked,
    muted,
    queueOpen,
    currentIndex,
    playTrack,
    loadIndex,
    togglePlay: () => setPlaying((value) => !value),
    seek: (seconds) =>
      setElapsed(Math.max(0, Math.min(current.duration, seconds))),
    next,
    previous,
    toggleLike: () => setLiked((value) => !value),
    toggleMute: () => setMuted((value) => !value),
    toggleQueue: () => setQueueOpen((value) => !value),
  };

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}

export function usePlayer() {
  const context = useContext(PlayerContext);
  if (!context) {
    throw new Error("usePlayer must be used inside PlayerProvider");
  }
  return context;
}
