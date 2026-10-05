/** iOS Now Playing / lock screen diagnostics — posted to playback_events.detail */

export type NowPlayingDiagInput = {
  token?: string | null;
  reason: string;
  media?: HTMLMediaElement | null;
  uiPlaying?: boolean;
  refPlaying?: boolean;
  graphPlaying?: boolean;
  catalogDuration?: number;
  computedPlaying?: boolean;
  syncResult?: {
    playbackState?: string;
    positionOk?: boolean;
    positionError?: string;
    hadMetadata?: boolean;
  };
};

const READY_STATE = ['none', 'metadata', 'current', 'future', 'enough'] as const;
const NETWORK_STATE = ['empty', 'idle', 'loading', 'no_source'] as const;

function srcTail(src: string): string {
  const text = String(src || '').trim();
  if (!text) return '-';
  try {
    const path = text.startsWith('http') ? new URL(text).pathname : text;
    const parts = path.split('/').filter(Boolean);
    return parts.slice(-3).join('/') || path.slice(-48);
  } catch {
    return text.slice(-48);
  }
}

export function snapshotMediaElement(media: HTMLMediaElement | null | undefined) {
  if (!media) {
    return {
      tag: '-',
      inDom: false,
      paused: true,
      ended: false,
      readyState: -1,
      readyLabel: '-',
      networkState: -1,
      networkLabel: '-',
      currentTime: 0,
      duration: 0,
      muted: false,
      volume: 0,
      srcTail: '-',
      error: '-',
    };
  }
  const err = media.error;
  return {
    tag: media.tagName,
    inDom: typeof document !== 'undefined' && document.contains(media),
    paused: media.paused,
    ended: media.ended,
    readyState: media.readyState,
    readyLabel: READY_STATE[media.readyState] ?? String(media.readyState),
    networkState: media.networkState,
    networkLabel: NETWORK_STATE[media.networkState] ?? String(media.networkState),
    currentTime: media.currentTime || 0,
    duration: Number.isFinite(media.duration) ? media.duration : 0,
    muted: media.muted,
    volume: media.volume,
    srcTail: srcTail(media.currentSrc || media.getAttribute('src') || ''),
    error: err ? `${err.code}:${err.message || 'err'}` : '-',
  };
}

export function snapshotMediaSession() {
  if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) {
    return { supported: false, playbackState: '-', title: '-', artist: '-', hadMetadata: false };
  }
  const session = navigator.mediaSession;
  const meta = session.metadata;
  return {
    supported: true,
    playbackState: session.playbackState || '-',
    title: meta?.title?.slice(0, 40) || '-',
    artist: meta?.artist?.slice(0, 40) || '-',
    hadMetadata: Boolean(meta),
  };
}

export function formatNowPlayingDetail(input: NowPlayingDiagInput): string {
  const m = snapshotMediaElement(input.media);
  const ms = snapshotMediaSession();
  const sync = input.syncResult;
  const ui = input.uiPlaying ? 1 : 0;
  const ref = input.refPlaying ? 1 : 0;
  const graph = input.graphPlaying ? 1 : 0;
  const pin = input.catalogDuration ?? 0;
  const comp = input.computedPlaying ? 1 : 0;
  const vis =
    typeof document !== 'undefined' ? (document.hidden ? 'hidden' : 'visible') : '-';
  const flags: string[] = [];
  if (input.refPlaying && m.paused) flags.push('REF_ON_MEDIA_PAUSED');
  if (input.uiPlaying && m.paused) flags.push('UI_ON_MEDIA_PAUSED');
  if (input.computedPlaying === false && input.refPlaying) flags.push('COMPUTED_NOT_PLAYING');
  if (ms.supported && ms.playbackState === 'playing' && m.paused) flags.push('MS_ON_MEDIA_PAUSED');
  if (ms.supported && ms.playbackState === 'paused' && !m.paused) flags.push('MS_PAUSED_MEDIA_PLAYING');
  if (!m.inDom) flags.push('MEDIA_NOT_IN_DOM');
  if (sync?.positionOk === false) flags.push('POS_FAIL');
  if (m.ended) flags.push('MEDIA_ENDED');
  if (m.readyState < 2 && !m.paused) flags.push('PLAYING_NOT_READY');

  const parts = [
    `reason=${input.reason}`,
    `vis=${vis}`,
    `tag=${m.tag}`,
    `inDom=${m.inDom ? 1 : 0}`,
    `paused=${m.paused ? 1 : 0}`,
    `rs=${m.readyLabel}`,
    `ns=${m.networkLabel}`,
    `ct=${m.currentTime.toFixed(1)}`,
    `dur=${m.duration.toFixed(1)}`,
    `pin=${pin.toFixed(1)}`,
    `srcOk=${m.srcTail && m.srcTail !== '-' ? 1 : 0}`,
    `ui=${ui}`,
    `ref=${ref}`,
    `graph=${graph}`,
    `comp=${comp}`,
    `ms=${ms.playbackState}`,
    `meta=${ms.hadMetadata ? 1 : 0}`,
    sync?.positionOk != null ? `posOk=${sync.positionOk ? 1 : 0}` : null,
    sync?.positionError ? `posErr=${sync.positionError}` : null,
    flags.length ? `flags=${flags.join(',')}` : null,
  ].filter(Boolean);

  return parts.join(' ').slice(0, 500);
}

const lastSentAt = new Map<string, number>();
const MIN_INTERVAL_MS = 400;

export function shouldSendNowPlayingDiag(reason: string, force = false): boolean {
  if (force) return true;
  const now = Date.now();
  const last = lastSentAt.get(reason) ?? 0;
  if (now - last < MIN_INTERVAL_MS) return false;
  lastSentAt.set(reason, now);
  return true;
}

export type ReportNowPlayingDiag = (input: NowPlayingDiagInput & { force?: boolean }) => void;

export function createNowPlayingReporter(
  report: (input: { token?: string | null; event: 'now_playing_diag'; detail?: string }) => void,
): ReportNowPlayingDiag {
  return (input) => {
    if (!shouldSendNowPlayingDiag(input.reason, input.force)) return;
    report({
      token: input.token,
      event: 'now_playing_diag',
      detail: formatNowPlayingDetail(input),
    });
  };
}
