/** OS + browser → isolated player id. Pass UA in tests; defaults to navigator in the app. */

export const PLAYER_IDS = [
  'ios-chrome',
  'ios-safari',
  'ios-firefox',
  'macos-chrome',
  'macos-safari',
  'macos-firefox',
  'macos-edge',
  'win-chrome',
  'win-edge',
  'win-firefox',
  'android-chrome',
  'android-firefox',
  'default',
] as const;

export type PlayerId = (typeof PLAYER_IDS)[number];

export type DetectInput = {
  userAgent?: string;
  platform?: string;
  maxTouchPoints?: number;
  vendor?: string;
};

function readNavigator(): DetectInput {
  if (typeof navigator === 'undefined') return {};
  return {
    userAgent: navigator.userAgent || '',
    platform: navigator.platform || '',
    maxTouchPoints: navigator.maxTouchPoints || 0,
    vendor: navigator.vendor || '',
  };
}

export function isIosUserAgent(input: DetectInput): boolean {
  const ua = input.userAgent || '';
  if (/iPhone|iPad|iPod/i.test(ua)) return true;
  if (/CriOS|FxiOS|EdgiOS/i.test(ua)) return true;
  if (input.platform === 'MacIntel' && (input.maxTouchPoints || 0) > 1) return true;
  return false;
}

export function isAndroidUserAgent(input: DetectInput): boolean {
  return /Android/i.test(input.userAgent || '');
}

/** Real macOS only — iPadOS “desktop” UA is iOS. */
export function isMacOsUserAgent(input: DetectInput): boolean {
  if (isIosUserAgent(input)) return false;
  const ua = input.userAgent || '';
  const platform = input.platform || '';
  return /Macintosh|Mac OS X/i.test(ua) || platform === 'MacIntel' || platform === 'MacPPC';
}

export function isWindowsUserAgent(input: DetectInput): boolean {
  const ua = input.userAgent || '';
  const platform = input.platform || '';
  return /Windows|Win32|Win64/i.test(ua) || /^Win/i.test(platform);
}

export function detectPlayer(raw?: DetectInput): PlayerId {
  const input = { ...readNavigator(), ...raw };
  const ua = input.userAgent || '';

  if (isIosUserAgent(input)) {
    if (/CriOS/i.test(ua)) return 'ios-chrome';
    if (/FxiOS/i.test(ua)) return 'ios-firefox';
    return 'ios-safari';
  }

  if (isAndroidUserAgent(input)) {
    if (/Firefox/i.test(ua)) return 'android-firefox';
    return 'android-chrome';
  }

  if (isMacOsUserAgent(input)) {
    if (/Edg(?:e|A|iOS)?\//i.test(ua) || /Edg\//i.test(ua)) return 'macos-edge';
    if (/Firefox/i.test(ua)) return 'macos-firefox';
    if (/Chrome|Chromium/i.test(ua)) return 'macos-chrome';
    return 'macos-safari';
  }

  if (isWindowsUserAgent(input)) {
    if (/Edg(?:e|A|iOS)?\//i.test(ua) || /Edg\//i.test(ua)) return 'win-edge';
    if (/Firefox/i.test(ua)) return 'win-firefox';
    if (/Chrome|Chromium/i.test(ua) && !/Edg/i.test(ua)) return 'win-chrome';
    return 'default';
  }

  return 'default';
}

export function playerUsesNativeVideo(id: PlayerId): boolean {
  return (
    id === 'ios-chrome' ||
    id === 'ios-safari' ||
    id === 'ios-firefox' ||
    id === 'macos-chrome' ||
    id === 'macos-safari'
  );
}

export function playerPrefersSilentHold(id: PlayerId): boolean {
  return id === 'ios-chrome';
}
