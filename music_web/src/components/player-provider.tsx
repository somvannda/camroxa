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
import { decryptCamxoraChunk } from '@/lib/camxora-decrypt';
import {
  createLicenseSession,
  fetchEncryptedChunkRecord,
  reportPlaybackTrace,
  SegmentOutOfRangeError,
  sendLicenseHeartbeat,
  type LicenseSession,
} from '@/lib/content-license';
import {
  assignPlayerSilentHold,
  clearPlayerForNativeStream,
  createMpegMediaSource,
  ensureAudioContextRunning,
  ensurePlayerSilentHoldPlaying,
  ensurePlayerSilentHoldPlayingWithLog,
  errorDetail,
  friendlyPlaybackError,
  getSharedAudioContext,
  holdHtmlMediaGesture,
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
  shouldUseHlsPlayback,
  shouldUseIosHlsPlayback,
  shouldUseIosNativeVideoElement,
  shouldUseMpegMediaSource,
  shouldUseNativeHtmlPlayback,
  unlockMediaPlayback,
  startNativePlayback,
  syncIosChromeHoldPosition,
  primeIosChromeVideoGesture,
  waitForNativePlayReady,
  wipeBytes,
} from '@/lib/mpeg-playback';
import {
  bindMediaSessionHandlers,
  clearMediaSession,
  installMediaSessionLockScreenKeepalive,
  installMediaSessionVisibilityRefresh,
  publishLockScreenNowPlaying,
  setMediaSessionMetadata,
  syncMediaSessionPlayback,
} from '@/lib/media-session';
import { createNowPlayingReporter, formatNowPlayingDetail } from '@/lib/now-playing-debug';
import { StreamingMp3Decoder } from '@/lib/mp3-software-decode';

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

const CHUNK_CONCURRENCY = 3;

type WebAudioRamCache = {
  key: string;
  buffers: AudioBuffer[];
};

let webAudioRamCache: WebAudioRamCache | null = null;

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
  window.setTimeout(() => ping('heartbeat'), 12000 + Math.floor(Math.random() * 4000));
  heartbeatRef.current = window.setInterval(() => ping('heartbeat'), 12000 + Math.floor(Math.random() * 4000));
}

function appendSourceBuffer(sourceBuffer: SourceBuffer, data: Uint8Array): Promise<void> {
  return new Promise((resolve, reject) => {
    const onUpdate = () => {
      sourceBuffer.removeEventListener('updateend', onUpdate);
      sourceBuffer.removeEventListener('error', onError);
      resolve();
    };
    const onError = () => {
      sourceBuffer.removeEventListener('updateend', onUpdate);
      sourceBuffer.removeEventListener('error', onError);
      reject(new Error('SourceBuffer error'));
    };
    sourceBuffer.addEventListener('updateend', onUpdate);
    sourceBuffer.addEventListener('error', onError);
    sourceBuffer.appendBuffer(data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength) as ArrayBuffer);
  });
}

async function fetchAndDecryptChunk(
  session: LicenseSession,
  chunkIndex: number,
  signal?: AbortSignal,
): Promise<{ data: Uint8Array; chunkCount: number | null }> {
  if (!session.content_key || !session.segment_url) {
    throw new Error('License session is missing audio.');
  }
  let record: { data: ArrayBuffer; chunkCount: number | null };
  try {
    record = await fetchEncryptedChunkRecord(session.segment_url, chunkIndex, signal);
  } catch (err) {
    if (isAbortLike(err) || signal?.aborted) throw err;
    throw err;
  }
  try {
    const plain = await decryptCamxoraChunk(record.data, session.content_key, chunkIndex);
    return { data: plain, chunkCount: record.chunkCount };
  } catch (err) {
    if (isAbortLike(err) || signal?.aborted) throw err;
    const plain = await decryptCamxoraChunk(record.data, session.content_key, chunkIndex);
    return { data: plain, chunkCount: record.chunkCount };
  }
}

async function fetchRemainingChunksOrdered(
  session: LicenseSession,
  startChunk: number,
  initialExpected: number | null,
  token: number,
  loadToken: { current: number },
  signal: AbortSignal | undefined,
  onChunk: (index: number, data: Uint8Array) => Promise<void>,
): Promise<number | null> {
  let expected = initialExpected;
  let nextFetch = startChunk;
  let nextProcess = startChunk;
  const pending = new Map<number, Uint8Array>();
  const inFlight = new Set<number>();
  let finished = expected != null && startChunk >= expected;
  let processing = false;
  let settled = false;

  return new Promise<number | null>((resolve, reject) => {
    const settle = (fn: () => void) => {
      if (settled) return;
      settled = true;
      fn();
    };

    const maybeFinish = () => {
      if (finished && inFlight.size === 0 && !pending.has(nextProcess)) {
        settle(() => resolve(expected));
      }
    };

    const processLoop = async () => {
      if (processing) return;
      processing = true;
      try {
        while (pending.has(nextProcess)) {
          if (signal?.aborted || token !== loadToken.current) {
            settle(() => resolve(expected));
            return;
          }
          const data = pending.get(nextProcess)!;
          pending.delete(nextProcess);
          try {
            await onChunk(nextProcess, data);
          } catch (err) {
            settle(() => reject(err));
            return;
          }
          nextProcess += 1;
          if (expected != null && nextProcess >= expected) {
            finished = true;
          }
        }
      } finally {
        processing = false;
      }
      maybeFinish();
      pumpFetch();
    };

    const pumpFetch = () => {
      if (signal?.aborted || token !== loadToken.current) {
        finished = true;
        maybeFinish();
        return;
      }
      while (inFlight.size < CHUNK_CONCURRENCY && !finished) {
        const idx = nextFetch;
        if (expected != null && idx >= expected) break;
        nextFetch += 1;
        inFlight.add(idx);
        fetchAndDecryptChunk(session, idx, signal)
          .then((result) => {
            inFlight.delete(idx);
            if (signal?.aborted || token !== loadToken.current) {
              wipeBytes(result.data);
              maybeFinish();
              return;
            }
            if (result.chunkCount) expected = result.chunkCount;
            pending.set(idx, result.data);
            void processLoop();
          })
          .catch((err) => {
            inFlight.delete(idx);
            if (err instanceof SegmentOutOfRangeError) {
              finished = true;
              maybeFinish();
              pumpFetch();
              return;
            }
            if (isAbortLike(err) || signal?.aborted) {
              finished = true;
              maybeFinish();
              return;
            }
            settle(() => reject(err));
          });
      }
      maybeFinish();
    };

    pumpFetch();
  });
}

async function playPackagedWithMediaSource(
  audio: HTMLAudioElement,
  session: LicenseSession,
  token: number,
  loadToken: { current: number },
  objectUrlRef: { current: string | null },
  setPlaying: (value: boolean) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!session.content_key || !session.segment_url) {
    throw new Error('License session is missing audio.');
  }
  const mediaSource = createMpegMediaSource();
  const objectUrl = URL.createObjectURL(mediaSource);
  objectUrlRef.current = objectUrl;
  prepareHtmlAudio(audio);
  audio.loop = false;
  audio.src = objectUrl;
  await new Promise<void>((resolve, reject) => {
    const onOpen = () => resolve();
    mediaSource.addEventListener('sourceopen', onOpen, { once: true });
    window.setTimeout(() => reject(new Error('MediaSource timeout')), 8000);
  });
  if (token !== loadToken.current) return;
  const sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg');

  reportPlaybackTrace({
    token: session.token,
    event: 'play_chunks',
    detail: 'fetch_start',
  });

  let expected: number | null = null;
  const first = await fetchAndDecryptChunk(session, 0, signal);
  if (signal?.aborted || token !== loadToken.current) {
    wipeBytes(first.data);
    return;
  }
  if (first.chunkCount) expected = first.chunkCount;
  await appendSourceBuffer(sourceBuffer, first.data);
  wipeBytes(first.data);
  try {
    await audio.play();
    if (token === loadToken.current) setPlaying(true);
  } catch (err) {
    if (token === loadToken.current) setPlaying(false);
    throw err;
  }

  if (expected == null || expected > 1) {
    expected = await fetchRemainingChunksOrdered(
      session,
      1,
      expected,
      token,
      loadToken,
      signal,
      async (_index, data) => {
        if (signal?.aborted || token !== loadToken.current) {
          wipeBytes(data);
          return;
        }
        await appendSourceBuffer(sourceBuffer, data);
        wipeBytes(data);
      },
    );
  }

  if (signal?.aborted || token !== loadToken.current) return;
  if (mediaSource.readyState === 'open') {
    mediaSource.endOfStream();
  }
}

async function playPackagedWithWebAudio(
  graph: ProtectedAudioGraph,
  audio: HTMLAudioElement,
  session: LicenseSession,
  token: number,
  loadToken: { current: number },
  volume: number,
  muted: boolean,
  catalogDuration: number,
  cacheKey: string,
  onStarted: (info: { firstAudioMs: number; fromCache: boolean }) => void,
  signal?: AbortSignal,
): Promise<void> {
  const playStartMs = performance.now();

  if (webAudioRamCache?.key === cacheKey && webAudioRamCache.buffers.length) {
    graph.stop();
    graph.setPinnedDuration(catalogDuration);
    await graph.loadFromCache(webAudioRamCache.buffers, volume, muted);
    graph.markComplete();
    releaseHtmlMediaGesture();
    onStarted({
      firstAudioMs: Math.round(performance.now() - playStartMs),
      fromCache: true,
    });
    return;
  }

  if (webAudioRamCache?.key !== cacheKey) {
    webAudioRamCache = null;
  }

  const ramBuffers: AudioBuffer[] = [];
  graph.stop();
  graph.setPinnedDuration(catalogDuration);

  const ctx = getSharedAudioContext();
  const decoder = new StreamingMp3Decoder(ctx);
  await decoder.ready();

  try {
    holdHtmlMediaGesture();
    reportPlaybackTrace({
      token: session.token,
      event: 'play_chunks',
      detail: 'fetch_start',
    });

    let fetchIdx = 0;
    let firstBuffer: AudioBuffer | null = null;
    let expected: number | null = null;

    while (!firstBuffer && fetchIdx < 4096) {
      if (signal?.aborted || token !== loadToken.current) {
        return;
      }
      await ensureAudioContextRunning();
      holdHtmlMediaGesture();

      let result: { data: Uint8Array; chunkCount: number | null };
      try {
        result = await fetchAndDecryptChunk(session, fetchIdx, signal);
      } catch (err) {
        if (err instanceof SegmentOutOfRangeError) break;
        throw err;
      }
      if (result.chunkCount) expected = result.chunkCount;
      firstBuffer = decoder.decodeChunk(result.data);
      wipeBytes(result.data);
      fetchIdx += 1;
      if (!firstBuffer && expected != null && fetchIdx >= expected) break;
    }

    if (!firstBuffer) throw new Error('No audio chunks received.');

    await graph.appendDecoded(firstBuffer, volume, muted);
    ramBuffers.push(firstBuffer);
    releaseHtmlMediaGesture();

    const firstAudioMs = Math.round(performance.now() - playStartMs);
    reportPlaybackTrace({
      token: session.token,
      event: 'play_decode',
      detail: 'chunk=0',
    });
    onStarted({ firstAudioMs, fromCache: false });

    if (expected == null || fetchIdx < expected) {
      expected = await fetchRemainingChunksOrdered(
        session,
        fetchIdx,
        expected,
        token,
        loadToken,
        signal,
        async (_index, data) => {
          if (signal?.aborted || token !== loadToken.current) {
            wipeBytes(data);
            return;
          }
          const buffer = decoder.decodeChunk(data);
          wipeBytes(data);
          if (buffer) {
            await graph.appendDecoded(buffer, volume, muted);
            ramBuffers.push(buffer);
          }
        },
      );
    }

    if (signal?.aborted || token !== loadToken.current) {
      return;
    }

    graph.markComplete();
    webAudioRamCache = { key: cacheKey, buffers: ramBuffers };
    reportPlaybackTrace({
      token: session.token,
      event: 'play_chunks',
      detail: `count=${ramBuffers.length}`,
    });
  } finally {
    decoder.free();
  }
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
    const intervalMs = shouldUseIosHlsPlayback() ? 400 : isIosChrome() ? 250 : 1000;
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
    if (!shouldUseIosHlsPlayback()) return () => undefined;
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

      const useHls = shouldUseIosHlsPlayback();
      if (!useHls && !shouldUseMpegMediaSource()) {
        if (audio instanceof HTMLAudioElement) {
          assignPlayerSilentHold(audio);
        }
      } else {
        audio.loop = false;
      }

      reportPlaybackTrace({
        event: 'play_start',
        detail: `id=${track.id} packaged=${String(track.package_status || 'none')} mse=${shouldUseMpegMediaSource() ? '1' : '0'} hls=${useHls ? '1' : '0'} crios=${isIosChrome() ? '1' : '0'}`,
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
          if (shouldUseMpegMediaSource() && session.content_key && session.segment_url) {
            reportPlaybackTrace({
              token: session.token,
              event: 'play_path',
              detail: 'path=mse',
            });
            await playPackagedWithMediaSource(
              audio as HTMLAudioElement,
              session,
              token,
              loadTokenRef,
              objectUrlRef,
              setPlaying,
              playAbort.signal,
            );
            if (token !== loadTokenRef.current) return;
            releaseHtmlMediaGesture();
            startPositionHeartbeat(() => audio.currentTime || 0, session, heartbeatRef);
          } else if (
            shouldUseIosHlsPlayback() &&
            session.hls_url &&
            isTrustedPlayUrl(session.hls_url)
          ) {
            reportPlaybackTrace({
              token: session.token,
              event: 'play_path',
              detail: `path=hls_aes128 crios=${isIosChrome() ? '1' : '0'}`,
            });
            setMediaSessionMetadata({
              title: nextTrack.title,
              artist: nextTrack.artist_name,
              album: nextTrack.album_name,
              coverUrl: nextTrack.cover_url,
            });
            clearPlayerForNativeStream(audio);
            if (audio instanceof HTMLVideoElement) prepareHtmlVideo(audio);
            else prepareHtmlAudio(audio);
            audio.loop = false;
            audio.muted = muted;
            audio.volume = muted ? 0 : volume;
            audio.src = session.hls_url;
            const startedAt = performance.now();
            try {
              await startNativePlayback(audio);
            } catch (err) {
              if (!isAbortLike(err)) throw err;
            }
            if (token !== loadTokenRef.current) return;
            releaseHtmlMediaGesture();
            setPlaying(true);
            playingRef.current = true;
            publishLockScreenNowPlaying(
              {
                title: nextTrack.title,
                artist: nextTrack.artist_name,
                album: nextTrack.album_name,
                coverUrl: nextTrack.cover_url,
              },
              {
                playing: true,
                duration: catalogDurationRef.current,
                position: audio.currentTime || 0,
              },
            );
            syncNowPlayingFromRefs('hls_started', true);
            startMediaSessionTick();
            startPositionHeartbeat(() => audio.currentTime || 0, session, heartbeatRef);
            reportPlaybackTrace({
              token: session.token,
              event: 'play_ok',
              detail: `path=hls_aes128 first_audio_ms=${Math.round(performance.now() - startedAt)} ctx=${audio instanceof HTMLVideoElement ? 'video' : 'audio'}`,
            });
          } else if (shouldUseNativeHtmlPlayback()) {
            const playUrl =
              session.play_url || `/api/v3/web-music/licenses/play/${session.token}`;
            if (!isTrustedPlayUrl(playUrl)) {
              throw new Error('Untrusted packaged play URL.');
            }
            reportPlaybackTrace({
              token: session.token,
              event: 'play_path',
              detail: 'path=html_native',
            });
            setMediaSessionMetadata({
              title: nextTrack.title,
              artist: nextTrack.artist_name,
              album: nextTrack.album_name,
              coverUrl: nextTrack.cover_url,
            });
            clearPlayerForNativeStream(audio);
            if (audio instanceof HTMLVideoElement) prepareHtmlVideo(audio);
            else prepareHtmlAudio(audio);
            audio.loop = false;
            audio.muted = muted;
            audio.volume = muted ? 0 : volume;
            audio.src = playUrl;
            const htmlStartedAt = performance.now();
            try {
              await startNativePlayback(audio);
            } catch (err) {
              if (!isAbortLike(err)) throw err;
            }
            if (token !== loadTokenRef.current) return;
            releaseHtmlMediaGesture();
            setPlaying(true);
            playingRef.current = true;
            syncNowPlayingFromRefs('html_started', true);
            startMediaSessionTick();
            startPositionHeartbeat(() => audio.currentTime || 0, session, heartbeatRef);
            reportPlaybackTrace({
              token: session.token,
              event: 'play_ok',
              detail: `path=html_native first_audio_ms=${Math.round(performance.now() - htmlStartedAt)} ctx=${audio instanceof HTMLVideoElement ? 'video' : 'audio'}`,
            });
          } else if (session.content_key && session.segment_url) {
            const graph = ensureGraph();
            const cacheKey = ramCacheKey(parsePlaybackSubject(nextTrack));
            reportPlaybackTrace({
              token: session.token,
              event: 'play_path',
              detail: 'path=webaudio',
            });
            await playPackagedWithWebAudio(
              graph,
              audio,
              session,
              token,
              loadTokenRef,
              volume,
              muted,
              catalogDurationRef.current,
              cacheKey,
              ({ firstAudioMs, fromCache }) => {
                if (token !== loadTokenRef.current) return;
                if (fromCache) {
                  reportPlaybackTrace({
                    token: session.token,
                    event: 'play_path',
                    detail: 'path=webaudio_ram',
                  });
                }
                if (!graph.playing) {
                  setPlaying(false);
                  setError('Tap play again to start audio.');
                  return;
                }
                setPlaying(true);
                playingRef.current = true;
                ensurePlayerSilentHoldPlaying(audio);
                setMediaSessionMetadata({
                  title: nextTrack.title,
                  artist: nextTrack.artist_name,
                  album: nextTrack.album_name,
                  coverUrl: nextTrack.cover_url,
                });
                syncNowPlayingFromRefs('webaudio_started', true);
                startMediaSessionTick();
                startPositionHeartbeat(() => graph.currentTime, session, heartbeatRef);
                reportPlaybackTrace({
                  token: session.token,
                  event: 'play_ok',
                  detail: `path=webaudio first_audio_ms=${firstAudioMs} ctx=${getSharedAudioContext().state}`,
                });
                void sendLicenseHeartbeat({
                  token: session.token,
                  positionSeconds: graph.currentTime,
                  playbackRate: 1,
                  seq: 1,
                  sessionBind: session.session_bind,
                });
              },
              playAbort.signal,
            );
            if (token !== loadTokenRef.current) return;
            return;
          }
          if (token !== loadTokenRef.current) return;
          void sendLicenseHeartbeat({
            token: session.token,
            positionSeconds: audio.currentTime || 0,
            playbackRate: 1,
            seq: 1,
            sessionBind: session.session_bind,
          });
          return;
        } catch (err) {
          if (token !== loadTokenRef.current || playAbort.signal.aborted) return;
          reportPlaybackTrace({
            token: session?.token,
            event: 'play_error',
            detail: `stage=packaged ${errorDetail(err)} ctx=${getSharedAudioContext().state}`,
          });
          if (!isAbortLike(err)) {
            setError(friendlyPlaybackError(err));
          }
          setPlaying(false);
          return;
        }
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
        startPositionHeartbeat(() => audio.currentTime || 0, session, heartbeatRef);
      }
      prepareHtmlAudio(audio);
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
      {shouldUseIosNativeVideoElement() ? (
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
