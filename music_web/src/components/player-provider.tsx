'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useRouter } from 'next/navigation';

import { useAuth } from '@/components/auth-provider';
import { catalogStreamUrl, getPlayUrl, isTrustedPlayUrl, type StreamTrack } from '@/lib/streaming-api';
import { reportCriosHoldEvent, reportCriosSyncDiag } from '@/lib/crios-now-playing-debug';
import {
  createLicenseSession,
  reportPlaybackTrace,
  sendLicenseHeartbeat,
} from '@/lib/content-license';
import {
  assignPlayerSilentHold,
  ensureAudioContextRunning,
  ensurePlayerSilentHoldPlaying,
  ensurePlayerSilentHoldPlayingWithLog,
  errorDetail,
  friendlyPlaybackError,
  getSharedAudioContext,
  isAbortLike,
  isIosChrome,
  isLicensedStreamSrc,
  isPlayerSilentHoldAudio,
  pausePlayerSilentHold,
  prepareHtmlAudio,
  prepareHtmlVideo,
  ProtectedAudioGraph,
  releaseHtmlMediaGesture,
  shouldHandleHtmlAudioEvent,
  shouldUseMpegMediaSource,
  unlockMediaPlayback,
  syncIosChromeHoldPosition,
  primeIosChromeVideoGesture,
} from '@/lib/mpeg-playback';
import {
  getPlayBackend,
  detectPlayer,
  playerUsesNativeVideo,
  iosChromeFriendlyError,
  isUnsupportedSrcError,
} from '@/lib/players';
import {
  bindMediaSessionHandlers,
  clearMediaSession,
  installMediaSessionLockScreenKeepalive,
  installMediaSessionVisibilityRefresh,
  setMediaSessionMetadata,
  syncMediaSessionPlayback,
} from '@/lib/media-session';
import { createNowPlayingReporter, formatNowPlayingDetail } from '@/lib/now-playing-debug';

type PlayerState = {
  current: StreamTrack | null;
  queue: StreamTrack[];
  queueIndex: number;
  playing: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  muted: boolean;
  error: string | null;
  playError: string | null;
  playTrack: (track: StreamTrack, queue?: StreamTrack[]) => Promise<void>;
  playQueue: (tracks: StreamTrack[], startIndex?: number) => Promise<void>;
  playShuffled: (tracks: StreamTrack[]) => Promise<void>;
  toggle: () => void;
  next: () => void;
  previous: () => void;
  seek: (time: number) => void;
  setVolume: (value: number) => void;
  toggleMute: () => void;
};

const PlayerContext = createContext<PlayerState | null>(null);

function shuffleTracks(tracks: StreamTrack[]): StreamTrack[] {
  const copy = [...tracks];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function parsePlaybackSubject(track: StreamTrack): {
  subjectType: 'stream_track' | 'suno_task';
  subjectId: string;
  variant: 'ok' | 'alt';
} {
  if (track.subject_type === 'suno_task' || track.id.includes(':')) {
    const [id, variant] = track.id.split(':');
    return {
      subjectType: 'suno_task',
      subjectId: id,
      variant: variant === 'alt' ? 'alt' : 'ok',
    };
  }
  return {
    subjectType: 'stream_track',
    subjectId: track.id,
    variant: track.variant === 'alt' ? 'alt' : 'ok',
  };
}

function ramCacheKey(subject: ReturnType<typeof parsePlaybackSubject>): string {
  return `${subject.subjectType}:${subject.subjectId}:${subject.variant}`;
}

function startPositionHeartbeat(
  getPosition: () => number,
  session: { token: string; session_bind?: string },
  heartbeatRef: { current: number | null },
  heartbeatTimeoutRef: { current: number | null },
) {
  let seq = 0;
  const ping = (event: string) => {
    seq += 1;
    void sendLicenseHeartbeat({
      token: session.token,
      event,
      positionSeconds: getPosition(),
      playbackRate: 1,
      seq,
      sessionBind: session.session_bind,
    });
  };
  if (heartbeatTimeoutRef.current != null) window.clearTimeout(heartbeatTimeoutRef.current);
  heartbeatTimeoutRef.current = window.setTimeout(
    () => ping('heartbeat'),
    12000 + Math.floor(Math.random() * 4000),
  );
  heartbeatRef.current = window.setInterval(() => ping('heartbeat'), 12000 + Math.floor(Math.random() * 4000));
}

function readStoredVolume(): number {
  if (typeof window === 'undefined') return 0.85;
  const raw = window.localStorage.getItem('camxora-music-volume');
  const parsed = raw == null ? NaN : Number(raw);
  if (!Number.isFinite(parsed)) return 0.85;
  return Math.min(1, Math.max(0, parsed));
}

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const mediaRef = useRef<HTMLMediaElement | null>(null);
  const graphRef = useRef<ProtectedAudioGraph | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const heartbeatTimeoutRef = useRef<number | null>(null);
  const queueRef = useRef<StreamTrack[]>([]);
  const indexRef = useRef(-1);
  const loadTokenRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const playFromIndexRef = useRef<(index: number) => Promise<void>>(async () => undefined);
  const catalogDurationRef = useRef(0);
  const playingRef = useRef(false);
  const mediaTickRef = useRef<number | null>(null);
  const sessionTokenRef = useRef<string | null>(null);
  const uiTimeRef = useRef(0);
  const criosHoldListenerCleanupRef = useRef<(() => void) | null>(null);
  const mediaListenerCleanupRef = useRef<(() => void) | null>(null);
  const diagNowPlayingRef = useRef(
    createNowPlayingReporter((input) => reportPlaybackTrace(input)),
  );
  const syncNowPlayingRef = useRef<(reason: string, force?: boolean) => void>(() => undefined);
  const startMediaSessionTickRef = useRef<() => void>(() => undefined);

  const [current, setCurrent] = useState<StreamTrack | null>(null);
  const [queue, setQueue] = useState<StreamTrack[]>([]);
  const [queueIndex, setQueueIndex] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState(0.85);
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    uiTimeRef.current = currentTime;
  }, [currentTime]);

  const pinnedDurationSeconds = useCallback((): number => {
    const pin = catalogDurationRef.current;
    if (pin > 0) return pin;
    const fromTrack = current?.duration_seconds;
    return fromTrack != null && fromTrack > 0 ? fromTrack : 0;
  }, [current?.duration_seconds]);

  const syncNowPlayingFromRefs = useCallback(
    (reason: string, forceDiag = false) => {
      if (!current) return;
      const pin = pinnedDurationSeconds();
      const graph = graphRef.current;
      const media = mediaRef.current;
      const isWebAudio = Boolean(graph?.hasBuffer);
      const src = media?.currentSrc || media?.getAttribute('src') || '';
      const isNativeStream = !isWebAudio && isLicensedStreamSrc(src);
      const isPlaying = (() => {
        if (isWebAudio) return Boolean(graph?.playing);
        if (media) return !media.paused && !media.ended;
        return playingRef.current;
      })();
      const position = isWebAudio ? graph!.currentTime : media?.currentTime || 0;
      let holdSeek: ReturnType<typeof syncIosChromeHoldPosition> = null;
      if (isPlaying && isWebAudio && media instanceof HTMLAudioElement) {
        if (isIosChrome()) {
          void ensurePlayerSilentHoldPlayingWithLog(media).then((playHold) => {
            if (!playHold.ok || document.hidden) {
              reportCriosSyncDiag({
                token: sessionTokenRef.current,
                reason: `${reason}_hold_play`,
                force: true,
                graphTime: graph?.currentTime,
                uiTime: uiTimeRef.current,
                holdTime: media.currentTime,
                pinDuration: pin,
                graphPlaying: graph?.playing,
                uiPlaying: playingRef.current,
                holdPaused: media.paused,
                holdEnded: media.ended,
                holdLoop: media.loop,
                holdInDom: document.contains(media),
                ctxState: getSharedAudioContext().state,
                syncPosition: position,
                playHold,
              });
            }
          });
        } else {
          ensurePlayerSilentHoldPlaying(media);
        }
        if (isIosChrome()) {
          holdSeek = syncIosChromeHoldPosition(media, position);
        }
      }
      const syncResult = syncMediaSessionPlayback({
        playing: isPlaying,
        duration: pin,
        position,
      });
      if (isNativeStream && isPlaying && media && !media.paused) {
        setMediaSessionMetadata({
          title: current.title,
          artist: current.artist_name,
          album: current.album_name,
          coverUrl: current.cover_url,
        });
      }
      diagNowPlayingRef.current({
        token: sessionTokenRef.current,
        reason,
        force: forceDiag,
        media,
        uiPlaying: playing,
        refPlaying: playingRef.current,
        graphPlaying: graph?.playing,
        catalogDuration: pin,
        computedPlaying: isPlaying,
        syncResult: {
          playbackState: syncResult.playbackState,
          positionOk: syncResult.positionOk,
          positionError: syncResult.positionError,
        },
      });
      if (isIosChrome() && isWebAudio && graph) {
        const hold =
          media instanceof HTMLAudioElement && isPlayerSilentHoldAudio(media) ? media : null;
        reportCriosSyncDiag({
          token: sessionTokenRef.current,
          reason,
          force: forceDiag || document.hidden,
          graphTime: graph.currentTime,
          uiTime: uiTimeRef.current,
          holdTime: hold?.currentTime,
          pinDuration: pin,
          graphPlaying: graph.playing,
          uiPlaying: playingRef.current,
          holdPaused: hold?.paused,
          holdEnded: hold?.ended,
          holdLoop: hold?.loop,
          holdInDom: hold ? document.contains(hold) : false,
          ctxState: getSharedAudioContext().state,
          syncPosition: position,
          posOk: syncResult.positionOk,
          posErr: syncResult.positionError,
          holdSeek: holdSeek ?? undefined,
        });
      }
    },
    [current, playing, pinnedDurationSeconds],
  );

  syncNowPlayingRef.current = syncNowPlayingFromRefs;

  const stopMediaSessionTick = useCallback(() => {
    if (mediaTickRef.current != null) {
      window.clearInterval(mediaTickRef.current);
      mediaTickRef.current = null;
    }
  }, []);

  const startMediaSessionTick = useCallback(() => {
    stopMediaSessionTick();
    const playerId = detectPlayer();
    const intervalMs = playerUsesNativeVideo(playerId) ? (playerId === 'ios-chrome' ? 250 : 400) : 1000;
    mediaTickRef.current = window.setInterval(() => {
      syncNowPlayingFromRefs('tick', document.hidden);
    }, intervalMs);
  }, [stopMediaSessionTick, syncNowPlayingFromRefs]);

  startMediaSessionTickRef.current = startMediaSessionTick;

  const attachMediaListeners = useCallback((media: HTMLMediaElement) => {
    mediaListenerCleanupRef.current?.();

    const logMediaEvent = (evt: string, force = false) => {
      reportPlaybackTrace({
        token: sessionTokenRef.current,
        event: 'media_element_event',
        detail: formatNowPlayingDetail({
          token: sessionTokenRef.current,
          reason: `evt_${evt}`,
          media,
          uiPlaying: playingRef.current,
          refPlaying: playingRef.current,
        }),
      });
      if (force || evt === 'playing' || evt === 'pause' || evt === 'waiting') {
        diagNowPlayingRef.current({
          token: sessionTokenRef.current,
          reason: `evt_${evt}`,
          force: true,
          media,
          uiPlaying: playingRef.current,
          refPlaying: playingRef.current,
        });
      }
    };

    const lockPositionSyncAtRef = { current: 0 };

    const onTimeUpdate = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(media)) return;
      const t = media.currentTime || 0;
      setCurrentTime(t);
      const src = media.currentSrc || media.getAttribute('src') || '';
      if (document.hidden && isLicensedStreamSrc(src)) {
        const now = performance.now();
        if (now - lockPositionSyncAtRef.current >= 350) {
          lockPositionSyncAtRef.current = now;
          syncNowPlayingRef.current('lock_timeupdate', false);
        }
      }
    };
    const onDuration = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(media)) return;
      if (catalogDurationRef.current > 0) return;
      const next = media.duration;
      if (!Number.isFinite(next) || next === Infinity) return;
      setDuration(next);
    };
    const onPlaying = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(media)) return;
      playingRef.current = true;
      setPlaying(true);
      logMediaEvent('playing', true);
      syncNowPlayingRef.current('media_playing', true);
      startMediaSessionTickRef.current();
    };
    const onPlay = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(media)) return;
      setPlaying(true);
      logMediaEvent('play');
    };
    const onPause = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(media)) return;
      setPlaying(false);
      playingRef.current = false;
      logMediaEvent('pause', true);
      syncNowPlayingRef.current('media_pause', true);
    };
    const onWaiting = () => logMediaEvent('waiting');
    const onStalled = () => logMediaEvent('stalled');
    const onError = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(media)) return;
      if (media.error && isAbortLike(media.error)) return;
      if (detectPlayer() === 'ios-chrome' && isUnsupportedSrcError(media.error, media)) {
        reportPlaybackTrace({
          event: 'play_error',
          detail: `stage=media_element ios_chrome_defer ${errorDetail(media.error)} src=${media.getAttribute('src') || ''}`,
        });
        logMediaEvent('error', true);
        setPlaying(false);
        return;
      }
      if (media.error) {
        reportPlaybackTrace({
          event: 'play_error',
          detail: `stage=media_element ${errorDetail(media.error)} src=${media.getAttribute('src') || ''}`,
        });
        setError(friendlyPlaybackError(media.error));
      }
      setPlaying(false);
      logMediaEvent('error', true);
    };
    const onEnded = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(media)) return;
      const nextIndex = indexRef.current + 1;
      if (nextIndex < queueRef.current.length) {
        void playFromIndexRef.current(nextIndex);
        return;
      }
      setPlaying(false);
      setCurrentTime(0);
      logMediaEvent('ended');
    };

    media.addEventListener('timeupdate', onTimeUpdate);
    media.addEventListener('durationchange', onDuration);
    media.addEventListener('loadedmetadata', onDuration);
    media.addEventListener('playing', onPlaying);
    media.addEventListener('play', onPlay);
    media.addEventListener('pause', onPause);
    media.addEventListener('waiting', onWaiting);
    media.addEventListener('stalled', onStalled);
    media.addEventListener('error', onError);
    media.addEventListener('ended', onEnded);

    mediaListenerCleanupRef.current = () => {
      media.removeEventListener('timeupdate', onTimeUpdate);
      media.removeEventListener('durationchange', onDuration);
      media.removeEventListener('loadedmetadata', onDuration);
      media.removeEventListener('playing', onPlaying);
      media.removeEventListener('play', onPlay);
      media.removeEventListener('pause', onPause);
      media.removeEventListener('waiting', onWaiting);
      media.removeEventListener('stalled', onStalled);
      media.removeEventListener('error', onError);
      media.removeEventListener('ended', onEnded);
    };
  }, []);

  const attachCriosHoldListeners = useCallback((audio: HTMLAudioElement) => {
    if (!isIosChrome()) return;
    criosHoldListenerCleanupRef.current?.();
    const extra = () => ({
      graphTime: graphRef.current?.currentTime,
      uiTime: uiTimeRef.current,
    });
    const onPause = () => {
      reportCriosHoldEvent(sessionTokenRef.current, 'pause', audio, extra());
    };
    const onPlay = () => {
      reportCriosHoldEvent(sessionTokenRef.current, 'play', audio, extra());
    };
    const onWaiting = () => {
      reportCriosHoldEvent(sessionTokenRef.current, 'waiting', audio, extra());
    };
    const onStalled = () => {
      reportCriosHoldEvent(sessionTokenRef.current, 'stalled', audio, extra());
    };
    const onEnded = () => {
      reportCriosHoldEvent(sessionTokenRef.current, 'ended', audio, extra());
    };
    let lastTu = 0;
    const onTimeUpdate = () => {
      if (!isPlayerSilentHoldAudio(audio)) return;
      const now = performance.now();
      if (now - lastTu < 900) return;
      lastTu = now;
      reportCriosHoldEvent(sessionTokenRef.current, 'timeupdate', audio, extra());
    };
    audio.addEventListener('pause', onPause);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('waiting', onWaiting);
    audio.addEventListener('stalled', onStalled);
    audio.addEventListener('ended', onEnded);
    audio.addEventListener('timeupdate', onTimeUpdate);
    criosHoldListenerCleanupRef.current = () => {
      audio.removeEventListener('pause', onPause);
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('waiting', onWaiting);
      audio.removeEventListener('stalled', onStalled);
      audio.removeEventListener('ended', onEnded);
      audio.removeEventListener('timeupdate', onTimeUpdate);
    };
  }, []);

  const bindMediaRef = useCallback(
    (el: HTMLMediaElement | null) => {
      if (!el) return;
      mediaRef.current = el;
      if (el instanceof HTMLVideoElement) prepareHtmlVideo(el);
      else prepareHtmlAudio(el);
      attachMediaListeners(el);
      if (el instanceof HTMLAudioElement) attachCriosHoldListeners(el);
      diagNowPlayingRef.current({
        token: sessionTokenRef.current,
        reason: 'media_ref_bind',
        force: true,
        media: el,
        refPlaying: playingRef.current,
        uiPlaying: playing,
      });
    },
    [attachCriosHoldListeners, attachMediaListeners, playing],
  );

  useEffect(() => {
    playingRef.current = playing;
  }, [playing]);

  const toggleRef = useRef<() => void>(() => undefined);
  const nextRef = useRef<() => void>(() => undefined);
  const previousRef = useRef<() => void>(() => undefined);
  const seekRef = useRef<(time: number) => void>(() => undefined);

  useEffect(() => {
    setVolumeState(readStoredVolume());
  }, []);

  const ensureMediaElement = useCallback((): HTMLMediaElement => {
    const el = mediaRef.current;
    if (!el) {
      diagNowPlayingRef.current({
        token: sessionTokenRef.current,
        reason: 'media_missing',
        force: true,
        media: null,
      });
      throw new Error('In-DOM media element is not mounted yet.');
    }
    if (el instanceof HTMLVideoElement) prepareHtmlVideo(el);
    else prepareHtmlAudio(el);
    return el;
  }, []);

  const iosChromePositionSyncAtRef = useRef(0);

  const ensureGraph = useCallback(() => {
    if (graphRef.current) return graphRef.current;
    const graph = new ProtectedAudioGraph(getSharedAudioContext());
    graph.onEnded = () => {
      const nextIndex = indexRef.current + 1;
      if (nextIndex < queueRef.current.length) {
        void playFromIndexRef.current(nextIndex);
        return;
      }
      setPlaying(false);
      setCurrentTime(0);
    };
    graph.onTime = (seconds) => {
      setCurrentTime(seconds);
      if (!isIosChrome() || !graph.playing) return;
      const audio = mediaRef.current;
      let holdSeek: ReturnType<typeof syncIosChromeHoldPosition> = null;
      if (audio instanceof HTMLAudioElement) {
        holdSeek = syncIosChromeHoldPosition(audio, seconds);
      }
      if (document.hidden) {
        const now = performance.now();
        if (now - iosChromePositionSyncAtRef.current >= 200) {
          iosChromePositionSyncAtRef.current = now;
          const hold =
            audio instanceof HTMLAudioElement && isPlayerSilentHoldAudio(audio) ? audio : null;
          reportCriosSyncDiag({
            token: sessionTokenRef.current,
            reason: 'crios_graph_tick',
            force: true,
            graphTime: seconds,
            uiTime: uiTimeRef.current,
            holdTime: hold?.currentTime,
            pinDuration: catalogDurationRef.current,
            graphPlaying: true,
            uiPlaying: playingRef.current,
            holdPaused: hold?.paused,
            holdEnded: hold?.ended,
            holdLoop: hold?.loop,
            holdInDom: hold ? document.contains(hold) : false,
            ctxState: getSharedAudioContext().state,
            syncPosition: seconds,
            holdSeek: holdSeek ?? undefined,
          });
        }
      }
    };
    graphRef.current = graph;
    return graph;
  }, []);

  useEffect(() => {
    return () => {
      mediaListenerCleanupRef.current?.();
      mediaListenerCleanupRef.current = null;
      criosHoldListenerCleanupRef.current?.();
      criosHoldListenerCleanupRef.current = null;
      if (heartbeatRef.current != null) {
        window.clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (heartbeatTimeoutRef.current != null) {
        window.clearTimeout(heartbeatTimeoutRef.current);
        heartbeatTimeoutRef.current = null;
      }
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
      graphRef.current?.stop();
      abortRef.current?.abort();
      releaseHtmlMediaGesture();
    };
  }, []);

  useEffect(() => {
    const audio = mediaRef.current;
    const usingWebAudio = Boolean(graphRef.current?.hasBuffer);
    if (audio) {
      if (usingWebAudio) {
        audio.muted = false;
        audio.volume = 0.0001;
      } else {
        audio.muted = muted;
        audio.volume = muted ? 0 : volume;
      }
    }
    graphRef.current?.setGain(volume, muted);
  }, [muted, volume, playing]);

  useEffect(() => {
    if (!current) {
      stopMediaSessionTick();
      clearMediaSession();
      return;
    }
    setMediaSessionMetadata({
      title: current.title,
      artist: current.artist_name,
      album: current.album_name,
      coverUrl: current.cover_url,
    });
  }, [current, current?.cover_url, current?.title, current?.artist_name, current?.album_name, stopMediaSessionTick]);

  useEffect(() => {
    if (!current) return;
    syncNowPlayingFromRefs('state_effect');
    if (playing) {
      startMediaSessionTick();
    } else {
      stopMediaSessionTick();
    }
    return stopMediaSessionTick;
  }, [current, playing, syncNowPlayingFromRefs, startMediaSessionTick, stopMediaSessionTick]);

  useEffect(() => {
    return installMediaSessionVisibilityRefresh(() => {
      if (!current) return;
      if (document.hidden && graphRef.current?.playing) {
        const media = mediaRef.current;
        if (media instanceof HTMLAudioElement) {
          ensurePlayerSilentHoldPlaying(media);
          if (isIosChrome()) {
            syncIosChromeHoldPosition(media, graphRef.current.currentTime);
          }
        }
        void ensureAudioContextRunning();
      }
      const visReason = `visibility_${document.hidden ? 'hidden' : 'visible'}`;
      syncNowPlayingFromRefs(visReason, true);
      if (isIosChrome() && document.hidden && graphRef.current?.hasBuffer) {
        window.setTimeout(() => syncNowPlayingFromRefs('visibility_burst_1', true), 100);
        window.setTimeout(() => syncNowPlayingFromRefs('visibility_burst_2', true), 350);
      }
    });
  }, [current, syncNowPlayingFromRefs]);

  useEffect(() => {
    if (!playerUsesNativeVideo(detectPlayer())) return () => undefined;
    return installMediaSessionLockScreenKeepalive(() => {
      if (!current) return;
      syncNowPlayingFromRefs('ios_lock_keepalive', true);
    });
  }, [current, syncNowPlayingFromRefs]);

  const redirectToLogin = useCallback(() => {
    if (typeof window === 'undefined') return;
    const next = `${window.location.pathname}${window.location.search}`;
    router.push(`/login?next=${encodeURIComponent(next || '/')}`);
  }, [router]);

  const playFromIndex = useCallback(
    async (index: number) => {
      if (authLoading) return;
      if (!user) {
        redirectToLogin();
        return;
      }

      const tracks = queueRef.current;
      const track = tracks[index];
      if (!track) return;

      const audio = ensureMediaElement();
      unlockMediaPlayback(audio);
      if (audio instanceof HTMLVideoElement) {
        primeIosChromeVideoGesture(audio);
      }

      abortRef.current?.abort();
      const playAbort = new AbortController();
      abortRef.current = playAbort;
      const token = ++loadTokenRef.current;

      const subject = parsePlaybackSubject(track);
      const sessionPromise = createLicenseSession({
        subjectType: subject.subjectType,
        subjectId: subject.subjectId,
        variant: subject.variant,
      }).catch((err) => {
        reportPlaybackTrace({
          event: 'play_error',
          detail: `stage=session ${errorDetail(err)}`,
        });
        return null;
      });

      const playerId = detectPlayer();
      const backend = getPlayBackend(playerId);
      if (!backend.usesNativeVideo && !shouldUseMpegMediaSource()) {
        if (audio instanceof HTMLAudioElement) {
          assignPlayerSilentHold(audio);
        }
      } else {
        audio.loop = false;
      }

      reportPlaybackTrace({
        event: 'play_start',
        detail: `id=${track.id} packaged=${String(track.package_status || 'none')} player=${playerId} mse=${shouldUseMpegMediaSource() ? '1' : '0'} hls=${backend.usesNativeVideo ? '1' : '0'} crios=${playerId === 'ios-chrome' ? '1' : '0'}`,
      });

      indexRef.current = index;
      setQueueIndex(index);
      setCurrentTime(0);
      catalogDurationRef.current = track.duration_seconds ?? 0;
      setDuration(catalogDurationRef.current);
      setError(null);

      if (heartbeatRef.current != null) {
        window.clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (heartbeatTimeoutRef.current != null) {
        window.clearTimeout(heartbeatTimeoutRef.current);
        heartbeatTimeoutRef.current = null;
      }
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
      graphRef.current?.stop();

      let url = isTrustedPlayUrl(track.play_url ?? '') ? (track.play_url as string) : '';
      let nextTrack: StreamTrack = track;
      let packageStatus = String(track.package_status || 'none');
      const isCatalogTrack = !track.id.includes(':');
      if (!url && isCatalogTrack) {
        url = catalogStreamUrl(track.id);
      }

      const needsPlayUrl = !url || isCatalogTrack;
      const playUrlPromise = needsPlayUrl
        ? getPlayUrl(track.id).catch(() => null)
        : Promise.resolve(null);

      const applyPlayUrlPayload = (payload: Awaited<ReturnType<typeof getPlayUrl>> | null) => {
        if (!payload || token !== loadTokenRef.current) return;
        if (isTrustedPlayUrl(payload.url)) {
          url = payload.url;
        } else if (!url) {
          url = catalogStreamUrl(track.id);
        }
        packageStatus = payload.package_status || packageStatus;
        nextTrack = {
          ...track,
          title: payload.title ?? track.title,
          album_id: payload.album_id ?? track.album_id,
          album_name: payload.album_name ?? track.album_name,
          user_id: payload.user_id ?? track.user_id,
          artist_name: payload.artist_name ?? track.artist_name,
          cover_url: payload.cover_url ?? track.cover_url,
          duration_seconds: payload.duration_seconds ?? track.duration_seconds,
          play_count: payload.play_count ?? track.play_count,
          genre: payload.genre ?? track.genre,
          lyrics: payload.lyrics ?? track.lyrics,
          package_status: packageStatus,
          subject_type: payload.subject_type === 'suno_task' ? 'suno_task' : 'stream_track',
        };
        if (payload.duration_seconds != null && payload.duration_seconds > 0) {
          catalogDurationRef.current = payload.duration_seconds;
          setDuration(catalogDurationRef.current);
          graphRef.current?.setPinnedDuration(payload.duration_seconds);
        }
        setCurrent(nextTrack);
      };

      const session = await sessionPromise;
      if (token !== loadTokenRef.current) return;
      sessionTokenRef.current = session?.token ?? null;
      void playUrlPromise.then(applyPlayUrlPayload);

      setCurrent(nextTrack);
      if (audio instanceof HTMLVideoElement) prepareHtmlVideo(audio);
      else prepareHtmlAudio(audio);

      reportPlaybackTrace({
        token: session?.token,
        event: 'play_session',
        detail: `ready=${session?.ready ? '1' : '0'} package=${session?.package_status || packageStatus}`,
      });

      if (session?.ready && session.token) {
        try {
          await backend.play({
            playerId: backend.id,
            media: audio,
            session,
            track: nextTrack,
            token,
            loadToken: loadTokenRef,
            objectUrlRef,
            signal: playAbort.signal,
            volume,
            muted,
            catalogDuration: catalogDurationRef.current,
            ensureGraph,
            setPlaying,
            setError,
            playingRef,
            heartbeatRef,
            ramCacheKey: ramCacheKey(parsePlaybackSubject(nextTrack)),
            startPositionHeartbeat: (getPosition) => {
              startPositionHeartbeat(getPosition, session, heartbeatRef, heartbeatTimeoutRef);
            },
            startMediaSessionTick,
            syncNowPlayingFromRefs,
          });
          if (token !== loadTokenRef.current) return;
          return;
        } catch (err) {
          if (token !== loadTokenRef.current || playAbort.signal.aborted) return;
          reportPlaybackTrace({
            token: session?.token,
            event: 'play_error',
            detail: `stage=packaged player=${playerId} ${errorDetail(err)} ctx=${getSharedAudioContext().state}`,
          });
          if (!isAbortLike(err)) {
            setError(
              playerId === 'ios-chrome'
                ? iosChromeFriendlyError(err, audio)
                : friendlyPlaybackError(err),
            );
          }
          setPlaying(false);
          return;
        }
      }

      if (packageStatus === 'ready' || playerId === 'ios-chrome' || playerId === 'macos-chrome') {
        if (token === loadTokenRef.current) {
          setPlaying(false);
          setError(
            packageStatus === 'ready'
              ? 'This track is not ready to play yet.'
              : 'Playback is not available for this track.',
          );
        }
        return;
      }

      const payload = await playUrlPromise;
      applyPlayUrlPayload(payload);

      if (!url || !isTrustedPlayUrl(url)) {
        if (token === loadTokenRef.current) {
          setPlaying(false);
          setError(
            packageStatus === 'ready'
              ? 'This track is not ready to play yet.'
              : 'Playback is not available for this track.',
          );
        }
        return;
      }
      if (session) {
        startPositionHeartbeat(() => audio.currentTime || 0, session, heartbeatRef, heartbeatTimeoutRef);
      }
      if (audio instanceof HTMLVideoElement) prepareHtmlVideo(audio);
      else prepareHtmlAudio(audio);
      audio.loop = false;
      reportPlaybackTrace({
        token: session?.token,
        event: 'play_path',
        detail: `path=html url=${url}`,
      });
      audio.src = url;
      try {
        await audio.play();
        if (token === loadTokenRef.current) {
          setPlaying(true);
          setError(null);
          reportPlaybackTrace({
            token: session?.token,
            event: 'play_ok',
            detail: 'path=html',
          });
        }
      } catch (err) {
        if (token === loadTokenRef.current) {
          reportPlaybackTrace({
            token: session?.token,
            event: 'play_error',
            detail: `stage=html_play ${errorDetail(err)}`,
          });
          setPlaying(false);
          if (!isAbortLike(err)) {
            setError(friendlyPlaybackError(err));
          } else {
            setError('Tap play again to start audio.');
          }
        }
      }
    },
    [authLoading, ensureMediaElement, ensureGraph, muted, redirectToLogin, startMediaSessionTick, user, volume],
  );

  playFromIndexRef.current = playFromIndex;

  const setQueueAndPlay = useCallback(
    async (tracks: StreamTrack[], startIndex = 0) => {
      if (!tracks.length) return;
      const safeIndex = Math.min(Math.max(0, startIndex), tracks.length - 1);
      queueRef.current = tracks;
      setQueue(tracks);
      await playFromIndex(safeIndex);
    },
    [playFromIndex],
  );

  const playTrack = useCallback(
    async (track: StreamTrack, nextQueue?: StreamTrack[]) => {
      if (nextQueue?.length) {
        const index = nextQueue.findIndex((item) => item.id === track.id);
        await setQueueAndPlay(nextQueue, index >= 0 ? index : 0);
        return;
      }
      await setQueueAndPlay([track], 0);
    },
    [setQueueAndPlay],
  );

  const playQueue = useCallback(
    async (tracks: StreamTrack[], startIndex = 0) => {
      await setQueueAndPlay(tracks, startIndex);
    },
    [setQueueAndPlay],
  );

  const playShuffled = useCallback(
    async (tracks: StreamTrack[]) => {
      if (!tracks.length) return;
      await setQueueAndPlay(shuffleTracks(tracks), 0);
    },
    [setQueueAndPlay],
  );

  const toggle = useCallback(() => {
    const graph = graphRef.current;
    if (graph?.hasBuffer) {
      if (graph.playing) {
        graph.pause();
        if (mediaRef.current instanceof HTMLAudioElement) {
          pausePlayerSilentHold(mediaRef.current);
        }
        playingRef.current = false;
        setPlaying(false);
        syncNowPlayingFromRefs('toggle_pause', true);
      } else {
        unlockMediaPlayback(mediaRef.current);
        if (mediaRef.current instanceof HTMLAudioElement) {
          ensurePlayerSilentHoldPlaying(mediaRef.current);
        }
        setError(null);
        void graph.resume().then(() => {
          playingRef.current = true;
          setPlaying(true);
          if (mediaRef.current instanceof HTMLAudioElement) {
            ensurePlayerSilentHoldPlaying(mediaRef.current);
          }
          syncNowPlayingFromRefs('toggle_resume', true);
          startMediaSessionTick();
        }).catch((err) => {
          playingRef.current = false;
          setPlaying(false);
          syncNowPlayingFromRefs('toggle_pause', true);
          setError(friendlyPlaybackError(err));
        });
      }
      return;
    }
    const audio = mediaRef.current;
    if (!audio || !current) return;
    if (!shouldHandleHtmlAudioEvent(audio) && !graph?.hasBuffer) return;
    if (audio.paused) {
      unlockMediaPlayback(audio);
      setError(null);
      void audio
        .play()
        .then(() => {
          setPlaying(true);
          setError(null);
        })
        .catch((err) => {
          setPlaying(false);
          setError(friendlyPlaybackError(err));
        });
    } else {
      audio.pause();
      setPlaying(false);
    }
  }, [current, syncNowPlayingFromRefs, startMediaSessionTick]);

  const next = useCallback(() => {
    const nextIndex = indexRef.current + 1;
    if (nextIndex < queueRef.current.length) {
      void playFromIndex(nextIndex);
    }
  }, [playFromIndex]);

  const previous = useCallback(() => {
    const graph = graphRef.current;
    const audio = mediaRef.current;
    const position = graph?.hasBuffer ? graph.currentTime : audio?.currentTime || 0;
    if (position > 3) {
      if (graph?.hasBuffer) graph.seek(0);
      else if (audio) audio.currentTime = 0;
      setCurrentTime(0);
      return;
    }
    const prevIndex = indexRef.current - 1;
    if (prevIndex >= 0) {
      void playFromIndex(prevIndex);
    } else if (graph?.hasBuffer) {
      graph.seek(0);
      setCurrentTime(0);
    } else if (audio) {
      audio.currentTime = 0;
      setCurrentTime(0);
    }
  }, [playFromIndex]);

  const seek = useCallback((time: number) => {
    if (!Number.isFinite(time)) return;
    const graph = graphRef.current;
    if (graph?.hasBuffer) {
      const max = graph.decodedLength > 0 ? graph.decodedLength : graph.duration > 0 ? graph.duration : time;
      const nextTime = Math.min(Math.max(0, time), max);
      graph.seek(nextTime);
      setCurrentTime(nextTime);
      return;
    }
    const audio = mediaRef.current;
    if (!audio) return;
    const pin = catalogDurationRef.current;
    const max =
      pin > 0
        ? pin
        : Number.isFinite(audio.duration) && audio.duration > 0
          ? audio.duration
          : time;
    const nextTime = Math.min(Math.max(0, time), max);
    audio.currentTime = nextTime;
    setCurrentTime(nextTime);
  }, []);

  toggleRef.current = toggle;
  nextRef.current = next;
  previousRef.current = previous;
  seekRef.current = seek;

  useEffect(() => {
    return bindMediaSessionHandlers({
      onPlay: () => {
        reportPlaybackTrace({
          token: sessionTokenRef.current,
          event: 'media_element_event',
          detail: 'reason=lockscreen_play_action',
        });
        const graph = graphRef.current;
        if (graph?.hasBuffer) {
          if (graph.playing) return;
          unlockMediaPlayback(mediaRef.current);
          void graph.resume().then(() => {
            playingRef.current = true;
            setPlaying(true);
            ensurePlayerSilentHoldPlaying(mediaRef.current);
            syncNowPlayingFromRefs('lockscreen_play', true);
            startMediaSessionTick();
          }).catch(() => {
            playingRef.current = false;
            setPlaying(false);
            syncNowPlayingFromRefs('lockscreen_play_fail', true);
          });
          return;
        }
        const media = mediaRef.current;
        if (!media || !current) return;
        if (!media.paused) return;
        unlockMediaPlayback(media);
        void media.play().then(() => {
          playingRef.current = true;
          setPlaying(true);
          syncNowPlayingFromRefs('lockscreen_play', true);
          startMediaSessionTick();
        }).catch(() => {
          playingRef.current = false;
          setPlaying(false);
          syncNowPlayingFromRefs('lockscreen_play_fail', true);
        });
      },
      onPause: () => {
        reportPlaybackTrace({
          token: sessionTokenRef.current,
          event: 'media_element_event',
          detail: 'reason=lockscreen_pause_action',
        });
        const graph = graphRef.current;
        if (graph?.hasBuffer) {
          if (!graph.playing) return;
          graph.pause();
          if (mediaRef.current instanceof HTMLAudioElement) {
            pausePlayerSilentHold(mediaRef.current);
          }
          playingRef.current = false;
          setPlaying(false);
          syncNowPlayingFromRefs('lockscreen_pause', true);
          return;
        }
        const media = mediaRef.current;
        if (!media || media.paused) return;
        media.pause();
        playingRef.current = false;
        setPlaying(false);
        syncNowPlayingFromRefs('lockscreen_pause', true);
      },
      onPrevious: () => previousRef.current(),
      onNext: () => nextRef.current(),
      onSeek: (time) => seekRef.current(time),
      onSeekBackward: () => {
        const graph = graphRef.current;
        const media = mediaRef.current;
        const pin = catalogDurationRef.current;
        const pos = graph?.hasBuffer ? graph.currentTime : media?.currentTime || 0;
        const max = pin > 0 ? pin : pos + 15;
        seekRef.current(Math.max(0, pos - 15));
        syncNowPlayingFromRefs('lockscreen_seek_back', true);
      },
      onSeekForward: () => {
        const graph = graphRef.current;
        const media = mediaRef.current;
        const pin = catalogDurationRef.current;
        const pos = graph?.hasBuffer ? graph.currentTime : media?.currentTime || 0;
        const max = pin > 0 ? pin : pos + 15;
        seekRef.current(Math.min(max, pos + 15));
        syncNowPlayingFromRefs('lockscreen_seek_forward', true);
      },
    });
  }, [syncNowPlayingFromRefs, startMediaSessionTick]);

  const setVolume = useCallback((value: number) => {
    const nextVolume = Math.min(1, Math.max(0, value));
    setVolumeState(nextVolume);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('camxora-music-volume', String(nextVolume));
    }
    const audio = mediaRef.current;
    if (audio) {
      audio.muted = muted;
      audio.volume = muted ? 0 : nextVolume;
    }
    graphRef.current?.setGain(nextVolume, muted);
    if (nextVolume > 0 && muted) setMuted(false);
  }, [muted]);

  const toggleMute = useCallback(() => {
    setMuted((prev) => {
      const nextMuted = !prev;
      const audio = mediaRef.current;
      if (audio) {
        audio.muted = nextMuted;
        audio.volume = nextMuted ? 0 : volume;
      }
      graphRef.current?.setGain(volume, nextMuted);
      return nextMuted;
    });
  }, [volume]);

  const value = useMemo<PlayerState>(
    () => ({
      current,
      queue,
      queueIndex,
      playing,
      currentTime,
      duration,
      volume,
      muted,
      error,
      playError: error,
      playTrack,
      playQueue,
      playShuffled,
      toggle,
      next,
      previous,
      seek,
      setVolume,
      toggleMute,
    }),
    [
      current,
      queue,
      queueIndex,
      playing,
      currentTime,
      duration,
      volume,
      muted,
      error,
      playTrack,
      playQueue,
      playShuffled,
      toggle,
      next,
      previous,
      seek,
      setVolume,
      toggleMute,
    ],
  );

  return (
    <PlayerContext.Provider value={value}>
      {playerUsesNativeVideo(detectPlayer()) ? (
        <video
          ref={bindMediaRef}
          playsInline
          preload="auto"
          className="pointer-events-none fixed bottom-0 left-0 h-px w-px opacity-0"
          aria-hidden
        />
      ) : (
        <audio
          ref={bindMediaRef}
          playsInline
          preload="auto"
          className="pointer-events-none fixed bottom-0 left-0 h-px w-px opacity-0"
          aria-hidden
        />
      )}
      {children}
    </PlayerContext.Provider>
  );
}

export function usePlayer() {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider');
  return ctx;
}
