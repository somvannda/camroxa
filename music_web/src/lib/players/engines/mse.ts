import { reportPlaybackTrace, sendLicenseHeartbeat } from '@/lib/content-license';
import {
  createMpegMediaSource,
  prepareHtmlAudio,
  prepareHtmlVideo,
  releaseHtmlMediaGesture,
  wipeBytes,
} from '@/lib/mpeg-playback';

import type { PackagedPlayContext } from '../types';
import { fetchAndDecryptChunk, fetchRemainingChunksOrdered } from './chunks';

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

/** Desktop/Android Chrome-family only. Do not import from ios-chrome.ts. */
export async function playMseBackend(ctx: PackagedPlayContext): Promise<void> {
  const { media, session, token, loadToken, objectUrlRef, signal, setPlaying, playerId } = ctx;
  if (!session.content_key || !session.segment_url) {
    throw new Error('License session is missing audio.');
  }

  reportPlaybackTrace({
    token: session.token,
    event: 'play_path',
    detail: `path=mse player=${playerId}`,
  });

  const mediaSource = createMpegMediaSource();
  const objectUrl = URL.createObjectURL(mediaSource);
  objectUrlRef.current = objectUrl;
  if (media instanceof HTMLVideoElement) prepareHtmlVideo(media);
  else prepareHtmlAudio(media);
  media.loop = false;
  media.src = objectUrl;
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
  if (signal.aborted || token !== loadToken.current) {
    wipeBytes(first.data);
    return;
  }
  if (first.chunkCount) expected = first.chunkCount;
  await appendSourceBuffer(sourceBuffer, first.data);
  wipeBytes(first.data);
  try {
    await media.play();
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
        if (signal.aborted || token !== loadToken.current) {
          wipeBytes(data);
          return;
        }
        await appendSourceBuffer(sourceBuffer, data);
        wipeBytes(data);
      },
    );
  }

  if (signal.aborted || token !== loadToken.current) return;
  if (mediaSource.readyState === 'open') {
    mediaSource.endOfStream();
  }
  releaseHtmlMediaGesture();
  ctx.startPositionHeartbeat(() => media.currentTime || 0);
  void sendLicenseHeartbeat({
    token: session.token,
    positionSeconds: media.currentTime || 0,
    playbackRate: 1,
    seq: 1,
    sessionBind: session.session_bind,
  });
}
