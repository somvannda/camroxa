import { playMseBackend } from './engines/mse';
import type { PlayBackend } from './types';

export const androidChromeBackend: PlayBackend = {
  id: 'android-chrome',
  usesNativeVideo: false,
  play: playMseBackend,
};
