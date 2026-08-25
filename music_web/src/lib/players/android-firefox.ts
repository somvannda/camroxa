import { winFirefoxBackend } from './win-firefox';
import type { PlayBackend } from './types';

export const androidFirefoxBackend: PlayBackend = {
  ...winFirefoxBackend,
  id: 'android-firefox',
};
