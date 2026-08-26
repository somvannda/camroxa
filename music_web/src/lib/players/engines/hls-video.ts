import { reportPlaybackTrace, sendLicenseHeartbeat } from '@/lib/content-license';
import { publishLockScreenNowPlaying, setMediaSessionMetadata } from '@/lib/media-session';
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

export function hasTrustedHlsUrl(session: { hls_url?: string | null }): boolean {
  return Boolean(session.hls_url && isTrustedPlayUrl(session.hls_url));
}

export async function playHlsVideo(ctx: PackagedPlayContext): Promise<void> {
  const { media, session, track, token, loadToken, muted, volume, catalogDuration, playerId } = ctx;
  if (!session.hls_url || !isTrustedPlayUrl(session.hls_url)) {
    throw new Error('HLS URL is missing.');
  }

  reportPlaybackTrace({
    token: session.token,
    event: 'play_path',
    detail: `path=hls_aes128 player=${playerId}`,
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
  media.src = session.hls_url;
  const startedAt = performance.now();
  try {
    await startNativePlayback(media);
  } catch (err) {
    if (!isAbortLike(err)) throw err;
  }
  if (token !== loadToken.current) return;
  releaseHtmlMediaGesture();
  ctx.setPlaying(true);
  ctx.playingRef.current = true;
  publishLockScreenNowPlaying(
    {
      title: track.title,
      artist: track.artist_name,
      album: track.album_name,
      coverUrl: track.cover_url,
    },
    {
      playing: true,
      duration: catalogDuration,
      position: media.currentTime || 0,
    },
  );
  ctx.syncNowPlayingFromRefs('hls_started', true);
  ctx.startMediaSessionTick();
  ctx.startPositionHeartbeat(() => media.currentTime || 0);
  reportPlaybackTrace({
    token: session.token,
    event: 'play_ok',
    detail: `path=hls_aes128 player=${playerId} first_audio_ms=${Math.round(performance.now() - startedAt)} ctx=${media instanceof HTMLVideoElement ? 'video' : 'audio'}`,
  });
  void sendLicenseHeartbeat({
    token: session.token,
    positionSeconds: media.currentTime || 0,
    playbackRate: 1,
    seq: 1,
    sessionBind: session.session_bind,
  });
}
