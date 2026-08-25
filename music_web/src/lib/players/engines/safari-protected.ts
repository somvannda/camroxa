import { reportPlaybackTrace } from '@/lib/content-license';
import { errorDetail, isAbortLike } from '@/lib/mpeg-playback';

import { clearNativeMediaSrc } from './clear-src';
import { hasTrustedHlsUrl, playHlsVideo } from './hls-video';
import { playHtmlNative } from './html-native';
import { playWebAudioBackend } from './webaudio';
import type { PackagedPlayContext } from '../types';

/**
 * Safari-family protected play: HLS AES-128, then session HTML (server CXA1 decrypt),
 * then client CXA1 Web Audio. Never MSE.
 */
export async function playSafariProtected(ctx: PackagedPlayContext): Promise<void> {
  const { session, media, token, loadToken, signal, playerId } = ctx;
  const hasChunks = Boolean(session.content_key && session.segment_url);

  if (hasTrustedHlsUrl(session)) {
    try {
      await playHlsVideo(ctx);
      return;
    } catch (err) {
      if (isAbortLike(err) || signal.aborted) throw err;
      if (token !== loadToken.current) return;
      reportPlaybackTrace({
        token: session.token,
        event: 'play_path',
        detail: `path=safari_hls_fail_html_native player=${playerId} ${errorDetail(err)}`,
      });
      clearNativeMediaSrc(media);
    }
  }

  try {
    await playHtmlNative(ctx);
    return;
  } catch (err) {
    if (isAbortLike(err) || signal.aborted) throw err;
    if (token !== loadToken.current) return;
    if (!hasChunks) throw err;
    reportPlaybackTrace({
      token: session.token,
      event: 'play_path',
      detail: `path=safari_html_fail_webaudio player=${playerId} ${errorDetail(err)}`,
    });
    clearNativeMediaSrc(media);
  }

  if (hasChunks) {
    await playWebAudioBackend(ctx);
    return;
  }

  throw new Error('This track is not ready to play yet.');
}
