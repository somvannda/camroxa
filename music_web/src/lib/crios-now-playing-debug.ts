/** iOS Chrome (CriOS) Web Audio lock screen diagnostics — separate from Safari HLS. */

import { reportPlaybackTrace } from '@/lib/content-license';
import { isIosChrome, isPlayerSilentHoldAudio } from '@/lib/mpeg-playback';
import { snapshotMediaSession } from '@/lib/now-playing-debug';

export type HoldSeekResult = {
  from: number;
  target: number;
  after: number;
  ok: boolean;
  err?: string;
  skipped?: boolean;
};

export type CriosSyncDiagInput = {
  token?: string | null;
  reason: string;
  graphTime?: number;
  uiTime?: number;
  holdTime?: number;
  pinDuration?: number;
  graphPlaying?: boolean;
  uiPlaying?: boolean;
  holdPaused?: boolean;
  holdEnded?: boolean;
  holdLoop?: boolean;
  holdInDom?: boolean;
  ctxState?: string;
  syncPosition?: number;
  posOk?: boolean;
  posErr?: string;
  holdSeek?: HoldSeekResult;
  playHold?: { ok: boolean; err?: string };
};

const lastSentAt = new Map<string, number>();

function shouldSend(reason: string, force = false): boolean {
  if (force) return true;
  if (typeof document !== 'undefined' && document.hidden) return true;
  const now = Date.now();
  const last = lastSentAt.get(reason) ?? 0;
  if (now - last < 180) return false;
  lastSentAt.set(reason, now);
  return true;
}

export function formatCriosSyncDetail(input: CriosSyncDiagInput): string {
  const ms = snapshotMediaSession();
  const vis =
    typeof document !== 'undefined' ? (document.hidden ? 'hidden' : 'visible') : '-';
  const g = input.graphTime ?? 0;
  const u = input.uiTime ?? 0;
  const h = input.holdTime ?? 0;
  const pin = input.pinDuration ?? 0;
  const syncPos = input.syncPosition ?? g;
  const flags: string[] = [];

  if (input.graphPlaying && input.holdPaused) flags.push('GRAPH_ON_HOLD_PAUSED');
  if (Math.abs(g - u) > 1.5) flags.push('GRAPH_UI_DRIFT');
  if (Math.abs(g - h) > 1.5) flags.push('GRAPH_HOLD_DRIFT');
  if (Math.abs(syncPos - g) > 0.5) flags.push('SYNC_POS_DRIFT');
  if (input.posOk === false) flags.push('POS_FAIL');
  if (input.holdSeek && !input.holdSeek.ok && !input.holdSeek.skipped) flags.push('HOLD_SEEK_FAIL');
  if (input.playHold && !input.playHold.ok) flags.push('HOLD_PLAY_FAIL');
  if (input.ctxState && input.ctxState !== 'running') flags.push('CTX_NOT_RUNNING');
  if (ms.supported && ms.playbackState === 'paused' && input.graphPlaying) flags.push('MS_PAUSED_GRAPH_PLAYING');
  if (ms.supported && ms.playbackState === 'playing' && input.holdPaused) flags.push('MS_PLAYING_HOLD_PAUSED');

  const seek = input.holdSeek;
  const parts = [
    `reason=${input.reason}`,
    `vis=${vis}`,
    `g=${g.toFixed(1)}`,
    `ui=${u.toFixed(1)}`,
    `h=${h.toFixed(1)}`,
    `sync=${syncPos.toFixed(1)}`,
    `pin=${pin.toFixed(1)}`,
    `graph=${input.graphPlaying ? 1 : 0}`,
    `uiP=${input.uiPlaying ? 1 : 0}`,
    `holdP=${input.holdPaused ? 1 : 0}`,
    `holdE=${input.holdEnded ? 1 : 0}`,
    `loop=${input.holdLoop ? 1 : 0}`,
    `dom=${input.holdInDom ? 1 : 0}`,
    `ctx=${input.ctxState || '-'}`,
    `ms=${ms.playbackState}`,
    input.posOk != null ? `posOk=${input.posOk ? 1 : 0}` : null,
    input.posErr ? `posErr=${input.posErr.slice(0, 40)}` : null,
    seek && !seek.skipped
      ? `seek=${seek.from.toFixed(1)}>${seek.target.toFixed(1)}=${seek.after.toFixed(1)} ok=${seek.ok ? 1 : 0}${seek.err ? ` err=${seek.err.slice(0, 24)}` : ''}`
      : null,
    input.playHold ? `holdPlay=${input.playHold.ok ? 1 : 0}${input.playHold.err ? ` err=${input.playHold.err.slice(0, 24)}` : ''}` : null,
    flags.length ? `flags=${flags.join(',')}` : null,
  ].filter(Boolean);

  return parts.join(' ').slice(0, 500);
}

export function reportCriosSyncDiag(input: CriosSyncDiagInput & { force?: boolean }): void {
  if (!isIosChrome()) return;
  if (!shouldSend(input.reason, input.force)) return;
  reportPlaybackTrace({
    token: input.token,
    event: 'crios_sync_diag',
    detail: formatCriosSyncDetail(input),
  });
}

export function reportCriosHoldEvent(
  token: string | null | undefined,
  evt: string,
  audio: HTMLAudioElement | null | undefined,
  extra?: { graphTime?: number; uiTime?: number },
): void {
  if (!isIosChrome() || !audio || !isPlayerSilentHoldAudio(audio)) return;
  reportPlaybackTrace({
    token,
    event: 'crios_hold_event',
    detail: [
      `evt=${evt}`,
      `holdCt=${(audio.currentTime || 0).toFixed(1)}`,
      `paused=${audio.paused ? 1 : 0}`,
      `ended=${audio.ended ? 1 : 0}`,
      `loop=${audio.loop ? 1 : 0}`,
      extra?.graphTime != null ? `g=${extra.graphTime.toFixed(1)}` : null,
      extra?.uiTime != null ? `ui=${extra.uiTime.toFixed(1)}` : null,
      typeof document !== 'undefined' ? `vis=${document.hidden ? 'hidden' : 'visible'}` : null,
    ]
      .filter(Boolean)
      .join(' ')
      .slice(0, 500),
  });
}
