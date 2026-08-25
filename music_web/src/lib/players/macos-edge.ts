import { playMseBackend } from './engines/mse';
import type { PlayBackend } from './types';

export const macosEdgeBackend: PlayBackend = {
  id: 'macos-edge',
  usesNativeVideo: false,
  play: playMseBackend,
};
