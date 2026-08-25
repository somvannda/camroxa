import { playSafariProtected } from './engines/safari-protected';
import type { PlayBackend } from './types';

export const macosSafariBackend: PlayBackend = {
  id: 'macos-safari',
  usesNativeVideo: true,
  play: playSafariProtected,
};
