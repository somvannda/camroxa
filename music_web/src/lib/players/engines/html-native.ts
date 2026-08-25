import { reportPlaybackTrace, sendLicenseHeartbeat } from '@/lib/content-license';
import { setMediaSessionMetadata } from '@/lib/media-session';
import {
  clearPlayerForNativeStream,
  isAbortLike,
  prepareHtmlAudio,
  prepareHtmlVideo,
  releaseHtmlMediaGesture,
  startNativePlayback,
} from '@/lib/mpeg-playback';
import { isTrustedPlayUrl } from '@/lib/streaming-api';

import type { PackagedPlayContext } from '../types';

/** Safari-family fallback: session-bound HTML play stream. Never used by ios-chrome.ts. */
export async function playHtmlNative(ctx: PackagedPlayContext): Promise<void> {
  const { media, session, track, token, loadToken, muted, volume, playerId } = ctx;
  const playUrl = session.play_url || `/api/v1/web-music/licenses/play/${session.token}`;
  if (!isTrustedPlayUrl(playUrl)) {
    throw new Error('Untrusted packaged play URL.');
  }

  reportPlaybackTrace({
    token: session.token,
    event: 'play_path',
    detail: `path=html_native player=${playerId}`,
  });
  setMediaSessionMetadata({
    title: track.title,
    artist: track.artist_name,
    album: track.album_name,
    coverUrl: track.cover_url,
  });
  clearPlayerForNativeStream(media);
  if (media instanceof HTMLVideoElement) prepareHtmlVideo(media);
  else prepareHtmlAudio(media);
  media.loop = false;
  media.muted = muted;
  media.volume = muted ? 0 : volume;
  media.src = playUrl;
  const htmlStartedAt = performance.now();
  try {
    await startNativePlayback(media);
  } catch (err) {
    if (!isAbortLike(err)) throw err;
  }
  if (token !== loadToken.current) return;
  releaseHtmlMediaGesture();
  ctx.setPlaying(true);
  ctx.playingRef.current = true;
  ctx.syncNowPlayingFromRefs('html_started', true);
  ctx.startMediaSessionTick();
  ctx.startPositionHeartbeat(() => media.currentTime || 0);
  reportPlaybackTrace({
    token: session.token,
    event: 'play_ok',
    detail: `path=html_native player=${playerId} first_audio_ms=${Math.round(performance.now() - htmlStartedAt)} ctx=${media instanceof HTMLVideoElement ? 'video' : 'audio'}`,
  });
  void sendLicenseHeartbeat({
    token: session.token,
    positionSeconds: media.currentTime || 0,
    playbackRate: 1,
    seq: 1,
    sessionBind: session.session_bind,
  });
}
