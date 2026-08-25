import { canUseMpegMediaSource } from '@/lib/mpeg-playback';

import { playMseBackend } from './engines/mse';
import { playWebAudioBackend } from './engines/webaudio';
import type { PackagedPlayContext, PlayBackend } from './types';

async function playFirefoxFamily(ctx: PackagedPlayContext): Promise<void> {
  if (canUseMpegMediaSource() && ctx.session.content_key && ctx.session.segment_url) {
    await playMseBackend(ctx);
    return;
  }
  if (ctx.session.content_key && ctx.session.segment_url) {
    await playWebAudioBackend(ctx);
    return;
  }
  throw new Error('This track is not ready to play yet.');
}

export const winFirefoxBackend: PlayBackend = {
  id: 'win-firefox',
  usesNativeVideo: false,
  play: playFirefoxFamily,
};
