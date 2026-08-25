import { errorDetail, isAbortLike } from '@/lib/mpeg-playback';
import { reportPlaybackTrace } from '@/lib/content-license';

import { hasTrustedHlsUrl, playHlsVideo } from './engines/hls-video';
import { clearNativeMediaSrc } from './engines/clear-src';
import { playWebAudioBackend } from './engines/webaudio';
import { iosChromeFriendlyError } from './media-error';
import { resolveIosChromeLane } from './ios-chrome-plan';
import type { PackagedPlayContext, PlayBackend } from './types';

/**
 * macOS Chrome: HLS <video> first (not Windows MSE).
 * If HLS is missing or WebKit rejects it, decrypt CXA1 with Web Audio so every packaged song still plays.
 * Never html_native (Chrome MediaError 4 / theft-vector src).
 */
async function playMacosChrome(ctx: PackagedPlayContext): Promise<void> {
  const { session, media, token, loadToken, signal } = ctx;
  const hasChunks = Boolean(session.content_key && session.segment_url);
  const hasTrustedHls = hasTrustedHlsUrl(session);
  const initial = resolveIosChromeLane({
    hasTrustedHls,
    hlsAttemptFailed: false,
    hasPackagedChunks: hasChunks,
  });

  if (initial === 'hls') {
    try {
      await playHlsVideo(ctx);
      return;
    } catch (err) {
      if (isAbortLike(err) || signal.aborted) throw err;
      if (token !== loadToken.current) return;
      reportPlaybackTrace({
        token: session.token,
        event: 'play_path',
        detail: `path=macos_chrome_hls_fail_fallback_webaudio player=macos-chrome ${errorDetail(err)}`,
      });
      clearNativeMediaSrc(media);
    }
  } else if (initial === 'webaudio') {
    reportPlaybackTrace({
      token: session.token,
      event: 'play_path',
      detail: 'path=macos_chrome_no_hls_webaudio player=macos-chrome',
    });
  }

  const fallback = resolveIosChromeLane({
    hasTrustedHls,
    hlsAttemptFailed: true,
    hasPackagedChunks: hasChunks,
  });
  if (fallback === 'webaudio') {
    await playWebAudioBackend(ctx);
    return;
  }

  throw new Error(iosChromeFriendlyError(new Error('Media error 4'), media));
}

export const macosChromeBackend: PlayBackend = {
  id: 'macos-chrome',
  usesNativeVideo: true,
  play: playMacosChrome,
};
