import { playMseBackend } from './engines/mse';
import type { PlayBackend } from './types';

export const winEdgeBackend: PlayBackend = {
  id: 'win-edge',
  usesNativeVideo: false,
  play: playMseBackend,
};
