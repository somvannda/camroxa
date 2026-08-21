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
import { decryptCamxoraChunk } from '@/lib/camxora-decrypt';
import {
  createLicenseSession,
  fetchEncryptedChunkRecord,
  reportPlaybackTrace,
  SegmentOutOfRangeError,
  sendLicenseHeartbeat,
  type LicenseSession,
} from '@/lib/content-license';
import { Mp3PcmDecoder } from '@/lib/mp3-software-decode';
import {
  clearHtmlAudioSrc,
  createMpegMediaSource,
  ensureAudioContextRunning,
  errorDetail,
  friendlyPlaybackError,
  getSharedAudioContext,
  holdHtmlMediaGesture,
  isAbortLike,
  prepareHtmlAudio,
  ProtectedAudioGraph,
  releaseAudioContextHold,
  releaseHtmlMediaGesture,
  shouldHandleHtmlAudioEvent,
  shouldUseMpegMediaSource,
  unlockMediaPlayback,
  wipeBytes,
} from '@/lib/mpeg-playback';
import {
  applyNowPlayingMetadata,
  applyNowPlayingPosition,
  bindNowPlayingActions,
} from '@/lib/media-session';

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

function clipDurationOf(track: { duration_seconds?: number | null } | null | undefined): number {
  const n = Number(track?.duration_seconds);
  return Number.isFinite(n) && n > 0 ? n : 0;
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

const FETCH_CONCURRENCY = 3;

async function decryptOneChunk(
  session: LicenseSession,
  chunk: number,
  signal?: AbortSignal,
): Promise<{ plain: Uint8Array; chunkCount: number | null }> {
  if (!session.content_key || !session.segment_url) {
    throw new Error('License session is missing audio.');
  }
  const record = await fetchEncryptedChunkRecord(session.segment_url, chunk, signal);
  try {
    return {
      plain: await decryptCamxoraChunk(record.data, session.content_key, chunk),
      chunkCount: record.chunkCount,
    };
  } catch (err) {
    if (isAbortLike(err) || signal?.aborted) throw err;
    try {
      return {
        plain: await decryptCamxoraChunk(record.data, session.content_key, chunk),
        chunkCount: record.chunkCount,
      };
    } catch (retryErr) {
      throw new Error(`decrypt chunk ${chunk}: ${errorDetail(retryErr)}`);
    }
  }
}

async function mapPool<T, R>(items: T[], limit: number, fn: (item: T, index: number) => Promise<R>): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let next = 0;
  async function worker() {
    while (true) {
      const i = next;
      next += 1;
      if (i >= items.length) return;
      results[i] = await fn(items[i], i);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => worker()));
  return results;
}

async function loadChunkBatch(
  session: LicenseSession,
  start: number,
  count: number,
  token: number,
  loadToken: { current: number },
  signal?: AbortSignal,
): Promise<Array<{ plain: Uint8Array; chunkCount: number | null } | null>> {
  const indexes = Array.from({ length: count }, (_, i) => start + i);
  return mapPool(indexes, FETCH_CONCURRENCY, async (chunk) => {
    if (signal?.aborted || token !== loadToken.current) return null;
    await ensureAudioContextRunning();
    holdHtmlMediaGesture();
    try {
      return await decryptOneChunk(session, chunk, signal);
    } catch (err) {
      if (isAbortLike(err) || signal?.aborted || token !== loadToken.current) return null;
      if (err instanceof SegmentOutOfRangeError) return null;
      throw err;
    }
  });
}

async function playPackagedWithMediaSource(
  audio: HTMLAudioElement,
  session: LicenseSession,
  token: number,
  loadToken: { current: number },
  objectUrlRef: { current: string | null },
  setPlaying: (value: boolean) => void,
  signal: AbortSignal | undefined,
  onStarted: () => void,
): Promise<void> {
  if (!session.content_key || !session.segment_url) {
    throw new Error('License session is missing audio.');
  }
  const mediaSource = createMpegMediaSource();
  // MediaSource object URL is not a downloadable MP3. Never createObjectURL(audio/mpeg).
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
    detail: 'fetch_start path=mse',
  });
  const firstAt = performance.now();
  const first = await decryptOneChunk(session, 0, signal);
  if (signal?.aborted || token !== loadToken.current) {
    wipeBytes(first.plain);
    return;
  }
  await appendSourceBuffer(sourceBuffer, first.plain);
  wipeBytes(first.plain);
  try {
    await audio.play();
    if (token === loadToken.current) {
      setPlaying(true);
      onStarted();
      reportPlaybackTrace({
        token: session.token,
        event: 'play_ok',
        detail: `path=mse first_audio_ms=${Math.round(performance.now() - firstAt)}`,
      });
    }
  } catch (err) {
    if (token === loadToken.current) setPlaying(false);
    throw err;
  }
  let expected = first.chunkCount;
  let chunk = 1;
  while (expected == null || chunk < expected) {
    if (signal?.aborted || token !== loadToken.current) return;
    const batch = expected == null ? FETCH_CONCURRENCY : Math.min(FETCH_CONCURRENCY, expected - chunk);
    if (batch <= 0) break;
    const parts = await loadChunkBatch(session, chunk, batch, token, loadToken, signal);
    let stopped = false;
    for (const part of parts) {
      if (signal?.aborted || token !== loadToken.current) return;
      if (!part) {
        stopped = true;
        break;
      }
      if (part.chunkCount) expected = part.chunkCount;
      await appendSourceBuffer(sourceBuffer, part.plain);
      wipeBytes(part.plain);
      chunk += 1;
      if (expected != null && chunk >= expected) break;
    }
    if (stopped) break;
  }
  if (mediaSource.readyState === 'open') {
    mediaSource.endOfStream();
  }
}

async function playPackagedWithWebAudio(
  graph: ProtectedAudioGraph,
  session: LicenseSession,
  token: number,
  loadToken: { current: number },
  volume: number,
  muted: boolean,
  signal: AbortSignal | undefined,
  hooks: {
    onFirstAudio: (firstAudioMs: number, bufferedSeconds: number) => void;
  },
): Promise<void> {
  const decoder = new Mp3PcmDecoder();
  try {
    await decoder.ensure();
    reportPlaybackTrace({
      token: session.token,
      event: 'play_chunks',
      detail: 'fetch_start path=webaudio',
    });
    const firstAt = performance.now();
    const first = await decryptOneChunk(session, 0, signal);
    if (signal?.aborted || token !== loadToken.current) {
      wipeBytes(first.plain);
      return;
    }
    const ctx = await ensureAudioContextRunning();
    let pcm = decoder.decodeChunk(ctx, first.plain);
    wipeBytes(first.plain);
    let expected = first.chunkCount;
    let chunk = 1;
    if (!pcm) {
      const extra = await loadChunkBatch(session, 1, 1, token, loadToken, signal);
      const part = extra[0];
      if (!part) throw new Error('Unable to decode the first audio chunk.');
      if (part.chunkCount) expected = part.chunkCount;
      pcm = decoder.decodeChunk(ctx, part.plain);
      wipeBytes(part.plain);
      chunk = 2;
    }
    if (!pcm) throw new Error('Unable to decode the first audio chunk.');
    await graph.startFirst(pcm, volume, muted);
    reportPlaybackTrace({
      token: session.token,
      event: 'play_decode',
      detail: `chunk=0 seconds=${pcm.duration.toFixed(2)} rate=${pcm.sampleRate} ctx=${ctx.state}`,
    });
    hooks.onFirstAudio(Math.round(performance.now() - firstAt), graph.duration);
    while (expected == null || chunk < expected) {
      if (signal?.aborted || token !== loadToken.current) return;
      const batch = expected == null ? FETCH_CONCURRENCY : Math.min(FETCH_CONCURRENCY, expected - chunk);
      if (batch <= 0) break;
      const parts = await loadChunkBatch(session, chunk, batch, token, loadToken, signal);
      let stopped = false;
      for (const part of parts) {
        if (signal?.aborted || token !== loadToken.current) return;
        if (!part) {
          stopped = true;
          break;
        }
        if (part.chunkCount) expected = part.chunkCount;
        const more = decoder.decodeChunk(ctx, part.plain);
        wipeBytes(part.plain);
        if (more) graph.appendDecoded(more);
        chunk += 1;
        if (expected != null && chunk >= expected) break;
      }
      if (stopped) break;
    }
    if (signal?.aborted || token !== loadToken.current) return;
    graph.markComplete();
    reportPlaybackTrace({
      token: session.token,
      event: 'play_chunks',
      detail: `count=${chunk} seconds=${graph.duration.toFixed(1)}`,
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
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const graphRef = useRef<ProtectedAudioGraph | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const queueRef = useRef<StreamTrack[]>([]);
  const indexRef = useRef(-1);
  const loadTokenRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const packagedKeyRef = useRef<string | null>(null);
  const clipDurationRef = useRef(0);
  const playFromIndexRef = useRef<(index: number) => Promise<void>>(async () => undefined);

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
    setVolumeState(readStoredVolume());
  }, []);

  const ensureAudio = useCallback(() => {
    if (audioRef.current) {
      prepareHtmlAudio(audioRef.current);
      return audioRef.current;
    }
    const audio = new Audio();
    prepareHtmlAudio(audio);
    audioRef.current = audio;
    return audio;
  }, []);

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
      const cap = clipDurationRef.current;
      setCurrentTime(cap > 0 ? Math.min(seconds, cap) : seconds);
    };
    graphRef.current = graph;
    return graph;
  }, []);

  useEffect(() => {
    const audio = ensureAudio();

    const onTimeUpdate = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(audio)) return;
      setCurrentTime(audio.currentTime || 0);
    };
    const onDuration = () => {
      // Duration should only come from stored duration_seconds, never from audio element
      // This handler is kept for compatibility but does not update clipDurationRef
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(audio)) return;
      // Do not update duration from audio.duration - it may be wrong for keep-alive WAV
    };
    const onPlay = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(audio)) return;
      setPlaying(true);
    };
    const onPause = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(audio)) return;
      setPlaying(false);
    };
    const onError = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(audio)) return;
      if (audio.error && isAbortLike(audio.error)) return;
      if (audio.error) {
        reportPlaybackTrace({
          event: 'play_error',
          detail: `stage=audio_element ${errorDetail(audio.error)} src=${audio.getAttribute('src') || ''}`,
        });
        setError(friendlyPlaybackError(audio.error));
      }
      setPlaying(false);
    };
    const onEnded = () => {
      if (graphRef.current?.hasBuffer) return;
      if (!shouldHandleHtmlAudioEvent(audio)) return;
      const nextIndex = indexRef.current + 1;
      if (nextIndex < queueRef.current.length) {
        void playFromIndexRef.current(nextIndex);
        return;
      }
      setPlaying(false);
      setCurrentTime(0);
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('durationchange', onDuration);
    audio.addEventListener('loadedmetadata', onDuration);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);
    audio.addEventListener('error', onError);
    audio.addEventListener('ended', onEnded);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('durationchange', onDuration);
      audio.removeEventListener('loadedmetadata', onDuration);
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
      audio.removeEventListener('error', onError);
      audio.removeEventListener('ended', onEnded);
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
  }, [ensureAudio]);

  useEffect(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.muted = muted;
      audio.volume = muted ? 0 : volume;
    }
    graphRef.current?.setGain(volume, muted);
  }, [muted, volume]);

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

      const audio = ensureAudio();
      audio.loop = false;
      unlockMediaPlayback(audio);
      reportPlaybackTrace({
        event: 'play_start',
        detail: `id=${track.id} packaged=${String(track.package_status || 'none')} mse=${shouldUseMpegMediaSource() ? '1' : '0'}`,
      });

      abortRef.current?.abort();
      const playAbort = new AbortController();
      abortRef.current = playAbort;
      const token = ++loadTokenRef.current;
      indexRef.current = index;
      setQueueIndex(index);
      setCurrentTime(0);
      const clipStart = clipDurationOf(track);
      clipDurationRef.current = clipStart;
      setDuration(clipStart);
      setError(null);

      if (heartbeatRef.current != null) {
        window.clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
      const subjectEarly = parsePlaybackSubject(track);
      const packagedKey = `${subjectEarly.subjectType}:${subjectEarly.subjectId}:${subjectEarly.variant}`;
      const reusePcm =
        !shouldUseMpegMediaSource() &&
        packagedKeyRef.current === packagedKey &&
        Boolean(graphRef.current?.complete && graphRef.current.hasBuffer);
      if (!reusePcm) {
        graphRef.current?.stop();
        packagedKeyRef.current = null;
      }

      let url = isTrustedPlayUrl(track.play_url ?? '') ? (track.play_url as string) : '';
      let nextTrack: StreamTrack = track;
      let packageStatus = String(track.package_status || 'none');
      const isCatalogTrack = !track.id.includes(':');
      if (!url && isCatalogTrack) {
        url = catalogStreamUrl(track.id);
      }
      if (!url || isCatalogTrack) {
        try {
          const payload = await getPlayUrl(track.id);
          if (token !== loadTokenRef.current) return;
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
        } catch {
          if (token !== loadTokenRef.current) return;
          if (!url && packageStatus !== 'ready') {
            if (!user) redirectToLogin();
            return;
          }
        }
      }
      if (token !== loadTokenRef.current) return;

      setCurrent(nextTrack);
      const clipKnown = clipDurationOf(nextTrack);
      if (clipKnown > 0) {
        clipDurationRef.current = clipKnown;
        setDuration(clipKnown);
      }

      audio.muted = muted;
      audio.volume = muted ? 0 : volume;
      prepareHtmlAudio(audio);

      const subject = parsePlaybackSubject(nextTrack);
      let session: LicenseSession | null = null;
      try {
        session = await createLicenseSession({
          subjectType: subject.subjectType,
          subjectId: subject.subjectId,
          variant: subject.variant,
        });
      } catch (err) {
        reportPlaybackTrace({
          event: 'play_error',
          detail: `stage=session ${errorDetail(err)}`,
        });
      }
      if (token !== loadTokenRef.current) return;
      reportPlaybackTrace({
        token: session?.token,
        event: 'play_session',
        detail: `ready=${session?.ready ? '1' : '0'} package=${session?.package_status || packageStatus}`,
      });

      if (session?.ready && session.content_key && session.segment_url) {
        const useHls = isSafariMpegMseBroken() && Boolean(session.hls_url);
        try {
          if (useHls && session.hls_url) {
            // iOS Safari: use native HLS with session-bound playlist
            reportPlaybackTrace({
              token: session.token,
              event: 'play_path',
              detail: 'path=hls_native',
            });
            prepareHtmlAudio(audio);
            audio.loop = false;
            audio.src = session.hls_url;
            try {
              await audio.play();
              if (token === loadTokenRef.current) {
                setPlaying(true);
                releaseHtmlMediaGesture();
                startPositionHeartbeat(() => audio.currentTime || 0, session, heartbeatRef);
                reportPlaybackTrace({
                  token: session.token,
                  event: 'play_ok',
                  detail: 'path=hls_native',
                });
              }
            } catch (err) {
              if (token === loadTokenRef.current) {
                setPlaying(false);
                if (!isAbortLike(err)) {
                  setError(friendlyPlaybackError(err));
                }
              }
            }
            return;
          }
          if (shouldUseMpegMediaSource()) {
            reportPlaybackTrace({
              token: session.token,
              event: 'play_path',
              detail: 'path=mse',
            });
            await playPackagedWithMediaSource(
              audio,
              session,
              token,
              loadTokenRef,
              objectUrlRef,
              setPlaying,
              playAbort.signal,
              () => {
                if (token !== loadTokenRef.current) return;
                releaseHtmlMediaGesture();
                startPositionHeartbeat(() => audio.currentTime || 0, session, heartbeatRef);
              },
            );
            if (token !== loadTokenRef.current) return;
          } else {
            clearHtmlAudioSrc(audio);
            const graph = ensureGraph();
            if (reusePcm && graph.complete && graph.hasBuffer) {
              reportPlaybackTrace({
                token: session.token,
                event: 'play_path',
                detail: 'path=webaudio_ram',
              });
              graph.seek(0);
              await graph.resume();
              if (token !== loadTokenRef.current) return;
              releaseAudioContextHold();
              releaseHtmlMediaGesture();
              setPlaying(true);
              startPositionHeartbeat(() => graph.currentTime, session, heartbeatRef);
              reportPlaybackTrace({
                token: session.token,
                event: 'play_ok',
                detail: `path=webaudio_ram first_audio_ms=0 duration=${graph.duration.toFixed(1)} ctx=${getSharedAudioContext().state}`,
              });
            } else {
              reportPlaybackTrace({
                token: session.token,
                event: 'play_path',
                detail: 'path=webaudio',
              });
              await playPackagedWithWebAudio(
                graph,
                session,
                token,
                loadTokenRef,
                volume,
                muted,
                playAbort.signal,
                {
                  onFirstAudio: (firstAudioMs, bufferedSeconds) => {
                    if (token !== loadTokenRef.current) return;
                    releaseAudioContextHold();
                    releaseHtmlMediaGesture();
                    setPlaying(true);
                    startPositionHeartbeat(() => graph.currentTime, session, heartbeatRef);
                    reportPlaybackTrace({
                      token: session.token,
                      event: 'play_ok',
                      detail: `path=webaudio first_audio_ms=${firstAudioMs} buffered=${bufferedSeconds.toFixed(1)} clip=${(clipDurationRef.current || 0).toFixed(1)} ctx=${getSharedAudioContext().state}`,
                    });
                  },
                },
              );
              if (token !== loadTokenRef.current) return;
              if (graph.complete) packagedKeyRef.current = packagedKey;
              // Duration should only come from stored duration_seconds, never from graph
            }
          }
          if (token !== loadTokenRef.current) return;
          void sendLicenseHeartbeat({
            token: session.token,
            positionSeconds: shouldUseMpegMediaSource()
              ? audio.currentTime || 0
              : graphRef.current?.currentTime || 0,
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
    [authLoading, ensureAudio, ensureGraph, muted, redirectToLogin, user, volume],
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
        setPlaying(false);
      } else {
        unlockMediaPlayback(audioRef.current);
        setError(null);
        void graph.resume().then(() => setPlaying(true)).catch((err) => {
          setPlaying(false);
          setError(friendlyPlaybackError(err));
        });
      }
      return;
    }
    const audio = audioRef.current;
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
  }, [current]);

  const next = useCallback(() => {
    const nextIndex = indexRef.current + 1;
    if (nextIndex < queueRef.current.length) {
      void playFromIndex(nextIndex);
    }
  }, [playFromIndex]);

  const previous = useCallback(() => {
    const graph = graphRef.current;
    const audio = audioRef.current;
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
      const max = graph.duration > 0 ? graph.duration : time;
      const nextTime = Math.min(Math.max(0, time), max);
      graph.seek(nextTime);
      setCurrentTime(nextTime);
      return;
    }
    const audio = audioRef.current;
    if (!audio) return;
    const max = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : time;
    const nextTime = Math.min(Math.max(0, time), max);
    audio.currentTime = nextTime;
    setCurrentTime(nextTime);
  }, []);

  const setVolume = useCallback((value: number) => {
    const nextVolume = Math.min(1, Math.max(0, value));
    setVolumeState(nextVolume);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('camxora-music-volume', String(nextVolume));
    }
    const audio = audioRef.current;
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
      const audio = audioRef.current;
      if (audio) {
        audio.muted = nextMuted;
        audio.volume = nextMuted ? 0 : volume;
      }
      graphRef.current?.setGain(volume, nextMuted);
      return nextMuted;
    });
  }, [volume]);

  useEffect(() => {
    applyNowPlayingMetadata(current);
    applyNowPlayingPosition(audioRef.current, playing, { currentTime, duration });
  }, [current, playing, currentTime, duration]);

  useEffect(() => {
    return bindNowPlayingActions({
      play: () => {
        const graph = graphRef.current;
        if (graph?.hasBuffer) {
          if (!graph.playing) {
            unlockMediaPlayback(audioRef.current);
            void graph.resume().then(() => setPlaying(true)).catch(() => setPlaying(false));
          }
          return;
        }
        const audio = audioRef.current;
        if (!audio) return;
        void audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
      },
      pause: () => {
        const graph = graphRef.current;
        if (graph?.hasBuffer) {
          graph.pause();
          setPlaying(false);
          return;
        }
        audioRef.current?.pause();
        setPlaying(false);
      },
      next: () => {
        const nextIndex = indexRef.current + 1;
        if (nextIndex < queueRef.current.length) {
          void playFromIndexRef.current(nextIndex);
        }
      },
      previous: () => {
        const graph = graphRef.current;
        const audio = audioRef.current;
        const currentPosition = graph?.hasBuffer ? graph.currentTime : audio?.currentTime || 0;
        if (currentPosition > 3) {
          if (graph?.hasBuffer) graph.seek(0);
          else if (audio) audio.currentTime = 0;
          setCurrentTime(0);
          return;
        }
        const prevIndex = indexRef.current - 1;
        if (prevIndex >= 0) {
          void playFromIndexRef.current(prevIndex);
        }
      },
      seek: (time) => {
        const graph = graphRef.current;
        if (graph?.hasBuffer) {
          graph.seek(time);
          setCurrentTime(graph.currentTime);
          return;
        }
        const audio = audioRef.current;
        if (audio) audio.currentTime = time;
        setCurrentTime(time);
      },
      getCurrentTime: () =>
        graphRef.current?.hasBuffer
          ? graphRef.current.currentTime
          : audioRef.current?.currentTime || 0,
    });
  }, []);

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
      <audio
        ref={(el) => {
          if (el) {
            audioRef.current = el;
            prepareHtmlAudio(el);
          }
        }}
        playsInline
        preload="auto"
        className="pointer-events-none fixed bottom-0 left-0 h-px w-px opacity-0"
        aria-hidden
      />
      {children}
    </PlayerContext.Provider>
  );
}

export function usePlayer() {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider');
  return ctx;
}
