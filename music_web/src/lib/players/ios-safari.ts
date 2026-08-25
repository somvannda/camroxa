import { playSafariProtected } from './engines/safari-protected';
import type { PlayBackend } from './types';

export const iosSafariBackend: PlayBackend = {
  id: 'ios-safari',
  usesNativeVideo: true,
  play: playSafariProtected,
};
