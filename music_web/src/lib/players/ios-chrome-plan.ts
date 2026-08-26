export type IosChromeLane = 'hls' | 'webaudio' | 'unavailable';

/** Pure routing for tests. Never returns MSE. */
export function resolveIosChromeLane(input: {
  hasTrustedHls: boolean;
  hlsAttemptFailed: boolean;
  hasPackagedChunks: boolean;
}): IosChromeLane {
  if (input.hasTrustedHls && !input.hlsAttemptFailed) return 'hls';
  if (input.hasPackagedChunks) return 'webaudio';
  return 'unavailable';
}
