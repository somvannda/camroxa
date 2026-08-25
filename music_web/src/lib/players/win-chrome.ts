import { playMseBackend } from './engines/mse';
import type { PlayBackend } from './types';

export const winChromeBackend: PlayBackend = {
  id: 'win-chrome',
  usesNativeVideo: false,
  play: playMseBackend,
};
