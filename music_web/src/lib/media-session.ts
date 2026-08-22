/** Lock screen / Dynamic Island metadata for iOS WebKit playback. */

export type MediaSessionTrack = {
  title?: string | null;
  artist?: string | null;
  album?: string | null;
  coverUrl?: string | null;
  duration?: number;
  position?: number;
  playing?: boolean;
};

const LOCK_SCREEN_ARTWORK_SIZES = [96, 128, 256, 512, 1024] as const;

function resolveArtworkUrl(coverUrl: string | null | undefined): string | null {
  if (!coverUrl) return null;
  const trimmed = coverUrl.trim();
  if (!trimmed) return null;
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (typeof window === 'undefined') return trimmed;
  try {
    return new URL(trimmed, window.location.origin).href;
  } catch {
    return null;
  }
}

function inferArtworkMime(url: string): string {
  const path = url.split('?')[0]?.toLowerCase() ?? '';
  if (path.endsWith('.png')) return 'image/png';
  if (path.endsWith('.webp')) return 'image/webp';
  if (path.endsWith('.gif')) return 'image/gif';
  return 'image/jpeg';
}

/** iOS lock screen subtitle often reads "Artist (Album)" — matches native music apps. */
export function formatLockScreenArtistLine(artist: string | null | undefined, album: string | null | undefined): string {
  const a = (artist || '').trim();
  const b = (album || '').trim();
  if (!a) return b || 'Camxora Artist';
  if (!b || b === a) return a;
  return `${a} (${b})`;
}

function preloadCover(url: string) {
  if (typeof Image === 'undefined') return;
  for (const size of [256, 512, 1024]) {
    const img = new Image();
    img.decoding = 'async';
    img.src = url;
    img.sizes = `${size}px`;
  }
}

function buildArtworkEntries(artworkUrl: string): MediaImage[] {
  const type = inferArtworkMime(artworkUrl);
  return LOCK_SCREEN_ARTWORK_SIZES.map((size) => ({
    src: artworkUrl,
    sizes: `${size}x${size}`,
    type,
  }));
}

/** Metadata only — does not touch playbackState or position. */
export function setMediaSessionMetadata(track: MediaSessionTrack | null) {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return;
  const session = navigator.mediaSession;

  if (!track) {
    session.metadata = null;
    return;
  }

  const title = track.title?.trim() || 'Unknown title';
  const artistLine = formatLockScreenArtistLine(track.artist, track.album);
  const album = track.album?.trim() || '';
  const artworkUrl = resolveArtworkUrl(track.coverUrl);

  const artwork: MediaImage[] = [];
  if (artworkUrl) {
    preloadCover(artworkUrl);
    artwork.push(...buildArtworkEntries(artworkUrl));
  }

  session.metadata = new MediaMetadata({
    title,
    artist: artistLine,
    album,
    artwork,
  });
}

/** Full lock screen publish: artwork + playback state + scrubber position. */
export function publishLockScreenNowPlaying(
  track: MediaSessionTrack,
  playback: { playing: boolean; duration: number; position: number },
) {
  setMediaSessionMetadata(track);
  return syncMediaSessionPlayback(playback);
}

/** Playback state + scrubber. Duration must be the catalog pin, never decoded length. */
export function syncMediaSessionPlayback(input: {
  playing: boolean;
  duration: number;
  position: number;
}): { playbackState: string; positionOk: boolean; positionError?: string } {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) {
    return { playbackState: 'unsupported', positionOk: false, positionError: 'no_media_session' };
  }
  const state = input.playing ? 'playing' : 'paused';
  navigator.mediaSession.playbackState = state;
  if (!Number.isFinite(input.duration) || input.duration <= 0 || !Number.isFinite(input.position)) {
    return { playbackState: state, positionOk: false, positionError: 'bad_duration' };
  }
  try {
    navigator.mediaSession.setPositionState?.({
      duration: input.duration,
      playbackRate: 1,
      position: Math.min(Math.max(0, input.position), input.duration),
    });
    return { playbackState: state, positionOk: true };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { playbackState: state, positionOk: false, positionError: message.slice(0, 80) };
  }
}

export function clearMediaSession() {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return;
  navigator.mediaSession.metadata = null;
  navigator.mediaSession.playbackState = 'none';
  try {
    navigator.mediaSession.setPositionState?.(undefined);
  } catch {
    /* unsupported */
  }
}

/** @deprecated Use setMediaSessionMetadata + syncMediaSessionPlayback */
export function updateMediaSession(track: MediaSessionTrack | null) {
  if (!track) {
    clearMediaSession();
    return;
  }
  setMediaSessionMetadata(track);
  syncMediaSessionPlayback({
    playing: Boolean(track.playing),
    duration: track.duration ?? 0,
    position: track.position ?? 0,
  });
}

export function updateMediaSessionPosition(duration: number, position: number) {
  syncMediaSessionPlayback({ playing: true, duration, position });
}

export type MediaSessionHandlers = {
  onPlay?: () => void;
  onPause?: () => void;
  onPrevious?: () => void;
  onNext?: () => void;
  onSeek?: (time: number) => void;
  onSeekBackward?: () => void;
  onSeekForward?: () => void;
};

export function bindMediaSessionHandlers(handlers: MediaSessionHandlers) {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return () => undefined;
  const session = navigator.mediaSession;

  const set = (action: MediaSessionAction, fn: (() => void) | undefined) => {
    try {
      if (fn) {
        session.setActionHandler(action, fn);
      } else {
        session.setActionHandler(action, null);
      }
    } catch {
      /* action not supported */
    }
  };

  set('play', handlers.onPlay ? () => handlers.onPlay?.() : undefined);
  set('pause', handlers.onPause ? () => handlers.onPause?.() : undefined);
  set('previoustrack', handlers.onPrevious ? () => handlers.onPrevious?.() : undefined);
  set('nexttrack', handlers.onNext ? () => handlers.onNext?.() : undefined);
  set('seekbackward', handlers.onSeekBackward ? () => handlers.onSeekBackward?.() : undefined);
  set('seekforward', handlers.onSeekForward ? () => handlers.onSeekForward?.() : undefined);

  try {
    if (handlers.onSeek) {
      session.setActionHandler('seekto', (details) => {
        if (details.seekTime != null && Number.isFinite(details.seekTime)) {
          handlers.onSeek?.(details.seekTime);
        }
      });
    } else {
      session.setActionHandler('seekto', null);
    }
  } catch {
    /* seekto not supported */
  }

  return () => {
    set('play', undefined);
    set('pause', undefined);
    set('previoustrack', undefined);
    set('nexttrack', undefined);
    set('seekbackward', undefined);
    set('seekforward', undefined);
    try {
      session.setActionHandler('seekto', null);
    } catch {
      /* already cleared */
    }
  };
}

export function installMediaSessionVisibilityRefresh(onRefresh: () => void) {
  if (typeof document === 'undefined') return () => undefined;
  const refresh = () => onRefresh();
  document.addEventListener('visibilitychange', refresh);
  return () => document.removeEventListener('visibilitychange', refresh);
}

export function installMediaSessionLockScreenKeepalive(onTick: () => void) {
  if (typeof document === 'undefined') return () => undefined;
  const tick = () => {
    if (document.hidden) onTick();
  };
  document.addEventListener('visibilitychange', tick);
  const id = window.setInterval(tick, 2000);
  return () => {
    document.removeEventListener('visibilitychange', tick);
    window.clearInterval(id);
  };
}
