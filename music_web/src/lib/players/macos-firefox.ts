import { winFirefoxBackend } from './win-firefox';
import type { PlayBackend } from './types';

export const macosFirefoxBackend: PlayBackend = {
  ...winFirefoxBackend,
  id: 'macos-firefox',
};
