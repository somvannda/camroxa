import { reportPlaybackTrace, sendLicenseHeartbeat, SegmentOutOfRangeError } from '@/lib/content-license';
import { setMediaSessionMetadata } from '@/lib/media-session';
import { StreamingMp3Decoder } from '@/lib/mp3-software-decode';
import {
  assignPlayerSilentHold,
  ensureAudioContextRunning,
  ensurePlayerSilentHoldPlaying,
  getSharedAudioContext,
  holdHtmlMediaGesture,
  primeIosChromeVideoGesture,
  releaseHtmlMediaGesture,
  wipeBytes,
} from '@/lib/mpeg-playback';

import type { PackagedPlayContext } from '../types';
import { fetchAndDecryptChunk, fetchRemainingChunksOrdered } from './chunks';

type WebAudioRamCache = {
  key: string;
  buffers: AudioBuffer[];
};

let webAudioRamCache: WebAudioRamCache | null = null;

function restoreSilentHold(media: HTMLMediaElement) {
  if (media instanceof HTMLVideoElement) {
    primeIosChromeVideoGesture(media);
    return;
  }
  if (media instanceof HTMLAudioElement) {
    assignPlayerSilentHold(media);
    ensurePlayerSilentHoldPlaying(media);
  }
}

export async function playWebAudioBackend(ctx: PackagedPlayContext): Promise<void> {
  const {
    media,
    session,
    track,
    token,
    loadToken,
    signal,
    volume,
    muted,
    catalogDuration,
    ramCacheKey,
    playerId,
    setPlaying,
    setError,
    playingRef,
  } = ctx;
  if (!session.content_key || !session.segment_url) {
    throw new Error('License session is missing audio.');
  }

  const graph = ctx.ensureGraph();
  const playStartMs = performance.now();

  reportPlaybackTrace({
    token: session.token,
    event: 'play_path',
    detail: `path=webaudio player=${playerId}`,
  });

  const onStarted = (info: { firstAudioMs: number; fromCache: boolean }) => {
    if (token !== loadToken.current) return;
    if (info.fromCache) {
      reportPlaybackTrace({
        token: session.token,
        event: 'play_path',
        detail: `path=webaudio_ram player=${playerId}`,
      });
    }
    if (!graph.playing) {
      setPlaying(false);
      setError('Tap play again to start audio.');
      return;
    }
    setError(null);
    setPlaying(true);
    playingRef.current = true;
    restoreSilentHold(media);
    setMediaSessionMetadata({
      title: track.title,
      artist: track.artist_name,
      album: track.album_name,
      coverUrl: track.cover_url,
    });
    ctx.syncNowPlayingFromRefs('webaudio_started', true);
    ctx.startMediaSessionTick();
    ctx.startPositionHeartbeat(() => graph.currentTime);
    reportPlaybackTrace({
      token: session.token,
      event: 'play_ok',
      detail: `path=webaudio player=${playerId} first_audio_ms=${info.firstAudioMs} ctx=${getSharedAudioContext().state}`,
    });
    void sendLicenseHeartbeat({
      token: session.token,
      positionSeconds: graph.currentTime,
      playbackRate: 1,
      seq: 1,
      sessionBind: session.session_bind,
    });
  };

  if (webAudioRamCache?.key === ramCacheKey && webAudioRamCache.buffers.length) {
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

  if (webAudioRamCache?.key !== ramCacheKey) {
    webAudioRamCache = null;
  }

  const ramBuffers: AudioBuffer[] = [];
  graph.stop();
  graph.setPinnedDuration(catalogDuration);

  const audioCtx = getSharedAudioContext();
  const decoder = new StreamingMp3Decoder(audioCtx);
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
      if (signal.aborted || token !== loadToken.current) {
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
          if (signal.aborted || token !== loadToken.current) {
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

    if (signal.aborted || token !== loadToken.current) {
      return;
    }

    graph.markComplete();
    webAudioRamCache = { key: ramCacheKey, buffers: ramBuffers };
    reportPlaybackTrace({
      token: session.token,
      event: 'play_chunks',
      detail: `count=${ramBuffers.length}`,
    });
  } finally {
    decoder.free();
  }
}
