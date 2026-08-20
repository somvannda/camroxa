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
import { decryptCamxoraChunk, decryptCamxoraPackage, looksLikeCamxoraPackage } from '@/lib/camxora-decrypt';
import {
  createLicenseSession,
  fetchEncryptedChunk,
  fetchEncryptedPackage,
  sendLicenseHeartbeat,
} from '@/lib/content-license';
import {
  createMp3ObjectUrl,
  isIosPackagedPlayback,
  resumeSharedAudioContext,
  WebAudioPlayback,
} from '@/lib/ios-playback';
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

function startPositionHeartbeat(
  audio: HTMLAudioElement,
  session: { token: string; session_bind?: string },
  heartbeatRef: { current: number | null },
) {
  let seq = 0;
  const ping = (event: string) => {
    seq += 1;
    void sendLicenseHeartbeat({
      token: session.token,
      event,
      positionSeconds: audio.currentTime || 0,
      playbackRate: audio.playbackRate || 1,
      seq,
      sessionBind: session.session_bind,
    });
  };
  window.setTimeout(() => ping('heartbeat'), 12000 + Math.floor(Math.random() * 4000));
  heartbeatRef.current = window.setInterval(() => ping('heartbeat'), 12000 + Math.floor(Math.random() * 4000));
  audio.addEventListener('ended', () => ping('complete'), { once: true });
  audio.addEventListener('pause', () => ping('pause'), { once: true });
}

function concatBytes(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.byteLength, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.byteLength;
  }
  return out;
}

function mpegMseSupported(): boolean {
  if (typeof window === 'undefined' || isIosPackagedPlayback()) return false;
  const ctor =
    (window as unknown as { ManagedMediaSource?: typeof MediaSource }).ManagedMediaSource ??
    window.MediaSource;
  return Boolean(ctor?.isTypeSupported?.('audio/mpeg'));
}

function prepareAudioElement(audio: HTMLAudioElement) {
  audio.setAttribute('playsinline', 'true');
  audio.setAttribute('webkit-playsinline', 'true');
  audio.preload = 'auto';
}

function unlockAudioForGesture(_audio: HTMLAudioElement) {
  resumeSharedAudioContext();
}

async function decryptPackagedMp3(
  segmentUrl: string,
  contentKey: string,
  isCurrentLoad: () => boolean,
  sequential: boolean,
): Promise<Uint8Array> {
  try {
    const packaged = await fetchEncryptedPackage(segmentUrl);
    if (!isCurrentLoad()) return new Uint8Array();
    if (looksLikeCamxoraPackage(packaged)) {
      return await decryptCamxoraPackage(packaged, contentKey);
    }
  } catch {
    /* older APIs ignore full=1 and still return a single chunk */
  }
  const first = await fetchEncryptedChunk(segmentUrl, 0);
  if (!isCurrentLoad()) return new Uint8Array();
  const parts: Uint8Array[] = [await decryptCamxoraChunk(first.buffer, contentKey, 0)];
  const count = first.chunkCount ?? 0;
  if (count > 1) {
    if (sequential) {
      for (let chunk = 1; chunk < count; chunk += 1) {
        if (!isCurrentLoad()) return concatBytes(parts);
        const record = await fetchEncryptedChunk(segmentUrl, chunk);
        parts.push(await decryptCamxoraChunk(record.buffer, contentKey, chunk));
      }
    } else {
      const rest = await Promise.all(
        Array.from({ length: count - 1 }, (_, index) => index + 1).map(async (chunk) => {
          const record = await fetchEncryptedChunk(segmentUrl, chunk);
          return decryptCamxoraChunk(record.buffer, contentKey, chunk);
        }),
      );
      parts.push(...rest);
    }
  } else if (!count) {
    for (let chunk = 1; chunk < 4096; chunk += 1) {
      if (!isCurrentLoad()) return concatBytes(parts);
      try {
        const record = await fetchEncryptedChunk(segmentUrl, chunk);
        parts.push(await decryptCamxoraChunk(record.buffer, contentKey, chunk));
      } catch {
        break;
      }
    }
  }
  return concatBytes(parts);
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
  const objectUrlRef = useRef<string | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const queueRef = useRef<StreamTrack[]>([]);
  const indexRef = useRef(-1);
  const loadTokenRef = useRef(0);
  const playFromIndexRef = useRef<(index: number) => Promise<void>>(async () => undefined);
  const suppressMediaEventsRef = useRef(false);
  const webAudioRef = useRef<WebAudioPlayback | null>(null);

  const [current, setCurrent] = useState<StreamTrack | null>(null);
  const [queue, setQueue] = useState<StreamTrack[]>([]);
  const [queueIndex, setQueueIndex] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState(0.85);
  const [muted, setMuted] = useState(false);
  const [playError, setPlayError] = useState<string | null>(null);

  useEffect(() => {
    setVolumeState(readStoredVolume());
  }, []);

  const ensureAudio = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) {
      throw new Error('Audio element is not ready.');
    }
    prepareAudioElement(audio);
    return audio;
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    prepareAudioElement(audio);

    const onTimeUpdate = () => {
      if (suppressMediaEventsRef.current || webAudioRef.current) return;
      setCurrentTime(audio.currentTime || 0);
    };
    const onDuration = () => {
      if (suppressMediaEventsRef.current || webAudioRef.current) return;
      setDuration(Number.isFinite(audio.duration) ? audio.duration : 0);
    };
    const onPlay = () => {
      if (suppressMediaEventsRef.current) return;
      setPlaying(true);
    };
    const onPause = () => {
      if (suppressMediaEventsRef.current || webAudioRef.current) return;
      setPlaying(false);
    };
    const onEnded = () => {
      if (suppressMediaEventsRef.current || webAudioRef.current) return;
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
    audio.addEventListener('ended', onEnded);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('durationchange', onDuration);
      audio.removeEventListener('loadedmetadata', onDuration);
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
      audio.removeEventListener('ended', onEnded);
      if (heartbeatRef.current != null) {
        window.clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
      webAudioRef.current?.stop();
      webAudioRef.current = null;
    };
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const nextVolume = muted ? 0 : volume;
    audio.volume = nextVolume;
    webAudioRef.current?.setVolume(nextVolume);
  }, [muted, volume]);

  const redirectToLogin = useCallback(() => {
    if (typeof window === 'undefined') return;
    const next = `${window.location.pathname}${window.location.search}`;
    router.push(`/login?next=${encodeURIComponent(next || '/')}`);
  }, [router]);

  const redirectToVerifyEmail = useCallback(() => {
    if (typeof window === 'undefined' || !user?.email) return;
    const next = `${window.location.pathname}${window.location.search}`;
    router.replace(
      `/verify-email?email=${encodeURIComponent(user.email)}&next=${encodeURIComponent(next || '/')}`,
    );
  }, [router, user?.email]);

  const playFromIndex = useCallback(
    async (index: number) => {
      if (authLoading) return;
      if (!user) {
        redirectToLogin();
        return;
      }
      if (user.email_confirmed === false) {
        redirectToVerifyEmail();
        return;
      }

      const audio = ensureAudio();
      webAudioRef.current?.stop();
      webAudioRef.current = null;
      if (isIosPackagedPlayback()) {
        suppressMediaEventsRef.current = true;
      }
      unlockAudioForGesture(audio);

      const tracks = queueRef.current;
      const track = tracks[index];
      if (!track) return;

      const token = ++loadTokenRef.current;
      indexRef.current = index;
      setQueueIndex(index);
      setCurrentTime(0);
      setDuration(track.duration_seconds ?? 0);
      setPlayError(null);

      if (heartbeatRef.current != null) {
        window.clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
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

      prepareAudioElement(audio);
      audio.volume = muted ? 0 : volume;

      if (packageStatus === 'ready') {
        try {
          const subject = parsePlaybackSubject(nextTrack);
          const session = await createLicenseSession({
            subjectType: subject.subjectType,
            subjectId: subject.subjectId,
            variant: subject.variant,
          });
          if (token !== loadTokenRef.current) return;
          if (session.ready && session.content_key && session.segment_url) {
            audio.removeAttribute('crossorigin');
            const isCurrentLoad = () => token === loadTokenRef.current;
            if (mpegMseSupported()) {
              try {
                const mediaSource = new MediaSource();
                const objectUrl = URL.createObjectURL(mediaSource);
                objectUrlRef.current = objectUrl;
                audio.src = objectUrl;
                await new Promise<void>((resolve, reject) => {
                  const onOpen = () => resolve();
                  mediaSource.addEventListener('sourceopen', onOpen, { once: true });
                  window.setTimeout(() => reject(new Error('MediaSource timeout')), 8000);
                });
                if (!isCurrentLoad()) return;
                const sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg');
                for (let chunk = 0; chunk < 4096; chunk += 1) {
                  if (!isCurrentLoad()) return;
                  let encrypted: ArrayBuffer;
                  try {
                    encrypted = (await fetchEncryptedChunk(session.segment_url, chunk)).buffer;
                  } catch {
                    break;
                  }
                  const plain = await decryptCamxoraChunk(encrypted, session.content_key, chunk);
                  await appendSourceBuffer(sourceBuffer, plain);
                  if (chunk === 0) {
                    try {
                      await audio.play();
                      if (isCurrentLoad()) setPlaying(true);
                    } catch {
                      if (isCurrentLoad()) setPlaying(false);
                    }
                  }
                }
                if (mediaSource.readyState === 'open') {
                  mediaSource.endOfStream();
                }
                void sendLicenseHeartbeat({
                  token: session.token,
                  positionSeconds: audio.currentTime || 0,
                  playbackRate: audio.playbackRate || 1,
                  seq: 1,
                  sessionBind: session.session_bind,
                });
                startPositionHeartbeat(audio, session, heartbeatRef);
                return;
              } catch {
                if (objectUrlRef.current) {
                  URL.revokeObjectURL(objectUrlRef.current);
                  objectUrlRef.current = null;
                }
              }
            }
            if (!isCurrentLoad()) return;
            const iosPath = isIosPackagedPlayback();
            const mp3 = await decryptPackagedMp3(
              session.segment_url,
              session.content_key,
              isCurrentLoad,
              iosPath,
            );
            if (!isCurrentLoad() || mp3.byteLength < 16) {
              suppressMediaEventsRef.current = false;
              setPlayError('Could not decrypt this track.');
              setPlaying(false);
              return;
            }
            const mp3Copy = mp3.buffer.slice(
              mp3.byteOffset,
              mp3.byteOffset + mp3.byteLength,
            ) as ArrayBuffer;

            const attachWebAudio = async (): Promise<boolean> => {
              const web = await WebAudioPlayback.fromMp3(mp3Copy, muted ? 0 : volume);
              if (!web || !isCurrentLoad()) return false;
              audio.pause();
              audio.loop = false;
              webAudioRef.current = web;
              web.onTime = (time, dur) => {
                setCurrentTime(time);
                setDuration(dur);
              };
              web.onEnded = () => {
                const nextIndex = indexRef.current + 1;
                if (nextIndex < queueRef.current.length) {
                  void playFromIndexRef.current(nextIndex);
                  return;
                }
                setPlaying(false);
                setCurrentTime(0);
              };
              resumeSharedAudioContext();
              web.start(0);
              setDuration(web.duration);
              return true;
            };

            let started = false;
            if (iosPath) {
              try {
                started = await attachWebAudio();
              } catch (webErr) {
                console.warn('Web Audio packaged play failed', webErr);
              }
            }
            if (!started) {
              const objectUrl = createMp3ObjectUrl(mp3Copy);
              objectUrlRef.current = objectUrl;
              audio.loop = false;
              audio.src = objectUrl;
              try {
                await audio.play();
                started = true;
              } catch (playErr) {
                console.warn('HTMLAudio packaged play failed, trying Web Audio', playErr);
                try {
                  started = await attachWebAudio();
                } catch (webErr) {
                  console.warn('Web Audio packaged play failed', webErr);
                }
              }
            }
            suppressMediaEventsRef.current = false;
            if (!isCurrentLoad()) return;
            setPlaying(started);
            if (!started) {
              setPlayError('This track could not start on this browser. Try again.');
              return;
            }
            void sendLicenseHeartbeat({
              token: session.token,
              positionSeconds: audio.currentTime || 0,
              playbackRate: audio.playbackRate || 1,
              seq: 1,
              sessionBind: session.session_bind,
            });
            startPositionHeartbeat(audio, session, heartbeatRef);
            return;
          }
          suppressMediaEventsRef.current = false;
          setPlaying(false);
          setPlayError('Licensed audio is not ready for this track.');
          return;
        } catch (err) {
          console.error('Packaged playback failed', err);
          suppressMediaEventsRef.current = false;
          if (token !== loadTokenRef.current) return;
          setPlaying(false);
          setPlayError(err instanceof Error ? err.message : 'Packaged playback failed.');
          return;
        }
      }

      suppressMediaEventsRef.current = false;
      audio.loop = false;
      if (!url || !isTrustedPlayUrl(url)) {
        if (token === loadTokenRef.current) setPlaying(false);
        return;
      }
      try {
        const subject = parsePlaybackSubject(nextTrack);
        const session = await createLicenseSession({
          subjectType: subject.subjectType,
          subjectId: subject.subjectId,
          variant: subject.variant,
        });
        startPositionHeartbeat(audio, session, heartbeatRef);
      } catch {
        /* unpackaged play still proceeds without a session */
      }
      audio.crossOrigin = 'use-credentials';
      audio.src = url;
      try {
        await audio.play();
        if (token === loadTokenRef.current) setPlaying(true);
      } catch {
        if (token === loadTokenRef.current) setPlaying(false);
      }
    },
    [authLoading, ensureAudio, muted, redirectToLogin, redirectToVerifyEmail, user, volume],
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
    const web = webAudioRef.current;
    if (web) {
      if (web.playing) {
        web.pause();
        setPlaying(false);
      } else {
        web.start(web.currentTime);
        setPlaying(true);
      }
      return;
    }
    const audio = audioRef.current;
    if (!audio || !current) return;
    if (audio.paused) {
      void audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
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
    const web = webAudioRef.current;
    const audio = audioRef.current;
    const currentPosition = web?.currentTime ?? audio?.currentTime ?? 0;
    if (currentPosition > 3) {
      if (web) {
        web.seek(0);
      } else if (audio) {
        audio.currentTime = 0;
      }
      setCurrentTime(0);
      return;
    }
    const prevIndex = indexRef.current - 1;
    if (prevIndex >= 0) {
      void playFromIndex(prevIndex);
    } else if (web) {
      web.seek(0);
      setCurrentTime(0);
    } else if (audio) {
      audio.currentTime = 0;
      setCurrentTime(0);
    }
  }, [playFromIndex]);

  const seek = useCallback((time: number) => {
    if (!Number.isFinite(time)) return;
    const web = webAudioRef.current;
    if (web) {
      const nextTime = Math.min(Math.max(0, time), web.duration || time);
      web.seek(nextTime);
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
    if (audio) audio.volume = muted ? 0 : nextVolume;
    if (nextVolume > 0 && muted) setMuted(false);
  }, [muted]);

  const toggleMute = useCallback(() => {
    setMuted((prev) => {
      const nextMuted = !prev;
      const audio = audioRef.current;
      if (audio) audio.volume = nextMuted ? 0 : volume;
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
        const web = webAudioRef.current;
        if (web) {
          web.start(web.currentTime);
          setPlaying(true);
          return;
        }
        const audio = audioRef.current;
        if (!audio) return;
        void audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
      },
      pause: () => {
        const web = webAudioRef.current;
        if (web) {
          web.pause();
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
        const web = webAudioRef.current;
        const audio = audioRef.current;
        const currentPosition = web?.currentTime ?? audio?.currentTime ?? 0;
        if (currentPosition > 3) {
          if (web) web.seek(0);
          else if (audio) audio.currentTime = 0;
          setCurrentTime(0);
          return;
        }
        const prevIndex = indexRef.current - 1;
        if (prevIndex >= 0) {
          void playFromIndexRef.current(prevIndex);
        } else if (web) {
          web.seek(0);
          setCurrentTime(0);
        } else if (audio) {
          audio.currentTime = 0;
          setCurrentTime(0);
        }
      },
      seek: (time: number) => {
        if (!Number.isFinite(time)) return;
        const web = webAudioRef.current;
        if (web) {
          const nextTime = Math.min(Math.max(0, time), web.duration || time);
          web.seek(nextTime);
          setCurrentTime(nextTime);
          return;
        }
        const audio = audioRef.current;
        if (!audio) return;
        const max = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : time;
        const nextTime = Math.min(Math.max(0, time), max);
        audio.currentTime = nextTime;
        setCurrentTime(nextTime);
      },
      getCurrentTime: () => webAudioRef.current?.currentTime ?? audioRef.current?.currentTime ?? 0,
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
      playError,
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
      playError,
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

  useEffect(() => {
    if (typeof window === 'undefined') return;
    (window as unknown as { __camxoraPlayer?: Record<string, unknown> }).__camxoraPlayer = {
      playing,
      currentTime,
      duration,
      playError,
      title: current?.title ?? null,
      iosPath: isIosPackagedPlayback(),
      webAudio: Boolean(webAudioRef.current?.playing),
    };
  }, [playing, currentTime, duration, playError, current]);

  return (
    <PlayerContext.Provider value={value}>
      <audio
        ref={audioRef}
        playsInline
        preload="auto"
        className="pointer-events-none fixed bottom-0 left-0 h-px w-px opacity-0"
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
