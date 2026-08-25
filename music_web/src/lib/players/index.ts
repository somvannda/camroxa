import { androidChromeBackend } from './android-chrome';
import { androidFirefoxBackend } from './android-firefox';
import { defaultBackend } from './default';
import { detectPlayer, type PlayerId } from './detect';
import { iosChromeBackend } from './ios-chrome';
import { iosFirefoxBackend } from './ios-firefox';
import { iosSafariBackend } from './ios-safari';
import { macosChromeBackend } from './macos-chrome';
import { macosEdgeBackend } from './macos-edge';
import { macosFirefoxBackend } from './macos-firefox';
import { macosSafariBackend } from './macos-safari';
import type { PlayBackend } from './types';
import { winChromeBackend } from './win-chrome';
import { winEdgeBackend } from './win-edge';
import { winFirefoxBackend } from './win-firefox';

const BACKENDS: Record<PlayerId, PlayBackend> = {
  'ios-chrome': iosChromeBackend,
  'ios-safari': iosSafariBackend,
  'ios-firefox': iosFirefoxBackend,
  'macos-chrome': macosChromeBackend,
  'macos-safari': macosSafariBackend,
  'macos-firefox': macosFirefoxBackend,
  'macos-edge': macosEdgeBackend,
  'win-chrome': winChromeBackend,
  'win-edge': winEdgeBackend,
  'win-firefox': winFirefoxBackend,
  'android-chrome': androidChromeBackend,
  'android-firefox': androidFirefoxBackend,
  default: defaultBackend,
};

export function getPlayBackend(id?: PlayerId): PlayBackend {
  const resolved = id ?? detectPlayer();
  return BACKENDS[resolved] ?? defaultBackend;
}

export { detectPlayer, playerUsesNativeVideo } from './detect';
export type { PlayerId } from './detect';
export type { PackagedPlayContext, PlayBackend } from './types';
export { iosChromeFriendlyError, isUnsupportedSrcError } from './media-error';
