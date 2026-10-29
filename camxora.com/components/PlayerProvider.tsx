"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type Track = {
  title: string;
  artist: string;
  cover: string;
  duration: number;
  elapsed?: number;
  audioUrl?: string;
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
  enqueue: (track: Track) => void;
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
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const currentIndex = tracks.findIndex(
    (track) => track.title === current.title && track.artist === current.artist
  );

  useEffect(() => {
    const audio = new Audio();
    audio.preload = "metadata";
    audioRef.current = audio;
    const onTime = () => setElapsed(audio.currentTime);
    const onEnded = () => setPlaying(false);
    const onError = () => setPlaying(false);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("error", onError);
    return () => {
      audio.pause();
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("error", onError);
      audioRef.current = null;
    };
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.pause();
    if (current.audioUrl) {
      audio.src = current.audioUrl;
      audio.currentTime = Math.max(0, current.elapsed ?? 0);
      audio.load();
      if (playing) {
        void audio.play().catch(() => setPlaying(false));
      }
    } else {
      audio.removeAttribute("src");
      audio.load();
    }
  }, [current.audioUrl, current.title, current.artist]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !current.audioUrl) return;
    if (playing) {
      void audio.play().catch(() => setPlaying(false));
    } else {
      audio.pause();
    }
  }, [playing, current.audioUrl]);

  useEffect(() => {
    if (audioRef.current) audioRef.current.muted = muted;
  }, [muted]);

  useEffect(() => {
    if (!playing || current.audioUrl) return;
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
  }, [playing, current.audioUrl, current.duration]);

  const playTrack = (track: Track) => {    setTracks((items) =>
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

  /** Append a track to the play queue without starting playback. */
  const enqueue = (track: Track) => {
    setTracks((items) =>
      items.some(
        (item) => item.title === track.title && item.artist === track.artist
      )
        ? items
        : [...items, track]
    );
  };

  const loadIndex = (index: number) => {    const track = tracks[index];
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

  const togglePlay = () => {
    const audio = audioRef.current;
    if (current.audioUrl && audio) {
      if (playing) {
        audio.pause();
      } else {
        audio.currentTime = elapsed;
        void audio.play().catch(() => setPlaying(false));
      }
    }
    setPlaying((value) => !value);
  };

  const seek = (seconds: number) => {
    const next = Math.max(0, Math.min(current.duration, seconds));
    setElapsed(next);
    if (current.audioUrl && audioRef.current) {
      audioRef.current.currentTime = next;
    }
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
    enqueue,
    loadIndex,
    togglePlay,
    seek,
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
