import { errorDetail, isAbortLike } from '@/lib/mpeg-playback';
import { reportPlaybackTrace } from '@/lib/content-license';

import { hasTrustedHlsUrl, playHlsVideo } from './engines/hls-video';
import { clearNativeMediaSrc } from './engines/clear-src';
import { playWebAudioBackend } from './engines/webaudio';
import { iosChromeFriendlyError } from './media-error';
import { resolveIosChromeLane } from './ios-chrome-plan';
import type { PackagedPlayContext, PlayBackend } from './types';

export type { IosChromeLane } from './ios-chrome-plan';
export { resolveIosChromeLane } from './ios-chrome-plan';

async function playIosChrome(ctx: PackagedPlayContext): Promise<void> {
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
        detail: `path=ios_chrome_hls_fail_fallback_webaudio player=ios-chrome ${errorDetail(err)}`,
      });
      clearNativeMediaSrc(media);
    }
  } else if (initial === 'webaudio') {
    reportPlaybackTrace({
      token: session.token,
      event: 'play_path',
      detail: 'path=ios_chrome_no_hls_webaudio player=ios-chrome',
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

export const iosChromeBackend: PlayBackend = {
  id: 'ios-chrome',
  usesNativeVideo: true,
  play: playIosChrome,
};
