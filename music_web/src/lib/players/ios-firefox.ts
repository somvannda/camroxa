import { iosSafariBackend } from './ios-safari';
import type { PlayBackend } from './types';

/** FxiOS is WebKit; same HLS/native chain as Safari, isolated file. */
export const iosFirefoxBackend: PlayBackend = {
  ...iosSafariBackend,
  id: 'ios-firefox',
};
