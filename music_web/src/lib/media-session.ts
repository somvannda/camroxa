import type { StreamTrack } from '@/lib/streaming-api';

const FALLBACK_ARTWORK = '/camxora-now-playing.png';

function absolutize(url: string): string {
  const text = url.trim();
  if (!text) return '';
  if (/^https?:\/\//i.test(text)) return text;
  if (typeof window === 'undefined') return text;
  try {
    return new URL(text, window.location.origin).href;
  } catch {
    return text;
  }
}

function artworkType(url: string): string {
  const lower = url.toLowerCase();
  if (lower.includes('.svg')) return 'image/png';
  if (lower.includes('.png')) return 'image/png';
  if (lower.includes('.webp')) return 'image/webp';
  return 'image/jpeg';
}

function artworkFor(track: StreamTrack): MediaImage[] {
  const cover = absolutize(String(track.cover_url || '').trim());
  const fallback = absolutize(FALLBACK_ARTWORK);
  const src = cover && !cover.endsWith('.svg') ? cover : fallback;
  const type = artworkType(src);
  return [
    { src, sizes: '96x96', type },
    { src, sizes: '256x256', type },
    { src, sizes: '384x384', type },
    { src, sizes: '512x512', type },
  ];
}

export function applyNowPlayingMetadata(track: StreamTrack | null) {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return;
  if (!track) {
    navigator.mediaSession.metadata = null;
    return;
  }
  navigator.mediaSession.metadata = new MediaMetadata({
    title: track.title?.trim() || 'Camxora Music',
    artist: track.artist_name?.trim() || 'Camxora',
    album: track.album_name?.trim() || 'Camxora Music',
    artwork: artworkFor(track),
  });
}

export function applyNowPlayingPosition(
  audio: HTMLAudioElement | null,
  playing: boolean,
  fallback?: { currentTime: number; duration: number },
) {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return;
  navigator.mediaSession.playbackState = playing ? 'playing' : 'paused';
  const duration =
    fallback?.duration && fallback.duration > 0
      ? fallback.duration
      : audio && Number.isFinite(audio.duration)
        ? audio.duration
        : 0;
  const position =
    fallback && Number.isFinite(fallback.currentTime)
      ? fallback.currentTime
      : audio?.currentTime || 0;
  if (!Number.isFinite(duration) || duration <= 0 || !Number.isFinite(position)) return;
  try {
    navigator.mediaSession.setPositionState({
      duration,
      playbackRate: audio?.playbackRate || 1,
      position: Math.min(Math.max(0, position), duration),
    });
  } catch {
    /* iOS can throw if duration is still NaN */
  }
}

export function bindNowPlayingActions(handlers: {
  play: () => void;
  pause: () => void;
  next: () => void;
  previous: () => void;
  seek: (time: number) => void;
  getCurrentTime: () => number;
}) {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return () => undefined;
  const session = navigator.mediaSession;
  const skip = (delta: number) => handlers.seek(handlers.getCurrentTime() + delta);
  try {
    session.setActionHandler('play', handlers.play);
    session.setActionHandler('pause', handlers.pause);
    session.setActionHandler('stop', handlers.pause);
    session.setActionHandler('previoustrack', handlers.previous);
    session.setActionHandler('nexttrack', handlers.next);
    session.setActionHandler('seekbackward', () => skip(-10));
    session.setActionHandler('seekforward', () => skip(10));
    session.setActionHandler('seekto', (details) => {
      if (typeof details.seekTime === 'number') handlers.seek(details.seekTime);
    });
  } catch {
    /* some handlers are unsupported */
  }
  return () => {
    for (const action of [
      'play',
      'pause',
      'stop',
      'previoustrack',
      'nexttrack',
      'seekbackward',
      'seekforward',
      'seekto',
    ] as MediaSessionAction[]) {
      try {
        session.setActionHandler(action, null);
      } catch {
        /* ignore */
      }
    }
  };
}
