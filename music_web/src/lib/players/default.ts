import { canUseMpegMediaSource, isSafariMpegMseBroken } from '@/lib/mpeg-playback';

import { playMseBackend } from './engines/mse';
import { playWebAudioBackend } from './engines/webaudio';
import type { PackagedPlayContext, PlayBackend } from './types';

async function playDefault(ctx: PackagedPlayContext): Promise<void> {
  const mseOk =
    canUseMpegMediaSource() &&
    !isSafariMpegMseBroken() &&
    Boolean(ctx.session.content_key && ctx.session.segment_url);
  if (mseOk) {
    await playMseBackend(ctx);
    return;
  }
  if (ctx.session.content_key && ctx.session.segment_url) {
    await playWebAudioBackend(ctx);
    return;
  }
  throw new Error('This track is not ready to play yet.');
}

export const defaultBackend: PlayBackend = {
  id: 'default',
  usesNativeVideo: false,
  play: playDefault,
};
