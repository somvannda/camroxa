/** Web Create: 5s button lock, then another POST into the global server queue. */

export const CREATE_COOLDOWN_MS = 5_000;
export const CREATE_HARD_LOCK_MS = 5_000;
export const CREATE_MAX_QUEUE_PAID = 20;
export const CREATE_MAX_QUEUE_FREE = 2;
export const CREATE_MAX_QUEUE = CREATE_MAX_QUEUE_FREE;

export type WebMusicGenerateInput = {
  mode: 'simple' | 'advanced';
  lyrics?: string;
  style?: string;
  title?: string;
  prompt?: string;
  instrumental?: boolean;
  model?: 'V5' | 'V5_5';
  negative_tags?: string;
  vocal_gender?: 'm' | 'f' | 'both';
  style_weight?: number;
  weirdness_constraint?: number;
  audio_weight?: number;
  workspace_id?: string;
};

export function parseRetryAfterSeconds(value: string | null | undefined): number | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (/^\d+$/.test(trimmed)) {
    return Math.max(0, Number.parseInt(trimmed, 10));
  }
  const when = Date.parse(trimmed);
  if (Number.isNaN(when)) return null;
  return Math.max(0, Math.ceil((when - Date.now()) / 1000));
}

export function cooldownMsForAttempt(retryAfterSeconds: number | null | undefined): number {
  if (retryAfterSeconds != null && Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0) {
    return Math.max(CREATE_COOLDOWN_MS, Math.round(retryAfterSeconds * 1000));
  }
  return CREATE_COOLDOWN_MS;
}

export function remainingSeconds(untilMs: number, nowMs: number): number {
  return Math.max(0, Math.ceil((untilMs - nowMs) / 1000));
}

export function isHardLocked(hardLockUntilMs: number, nowMs: number): boolean {
  return nowMs < hardLockUntilMs;
}

export function isCoolingDown(cooldownUntilMs: number, nowMs: number): boolean {
  return nowMs < cooldownUntilMs;
}

export function queueLimitForUser(hasSubscription: boolean | null | undefined): number {
  return hasSubscription ? CREATE_MAX_QUEUE_PAID : CREATE_MAX_QUEUE_FREE;
}

export function createActionDisabled(input: {
  formReady: boolean;
  needsUpgrade: boolean;
  hardLocked: boolean;
  busy: boolean;
  coolingDown: boolean;
  queueUsed: number;
  queueLimit: number;
}): boolean {
  if (input.needsUpgrade || !input.formReady) return true;
  if (input.hardLocked || input.busy || input.coolingDown) return true;
  return input.queueUsed >= input.queueLimit;
}

export function createActionLabel(input: {
  busy: boolean;
  hardLocked: boolean;
  coolingDown: boolean;
  cooldownSeconds: number;
  queueUsed: number;
  queueLimit: number;
}): string {
  if (input.busy || input.hardLocked) return 'Creating…';
  if (input.coolingDown && input.cooldownSeconds > 0) return `Wait ${input.cooldownSeconds}s`;
  if (input.queueUsed >= input.queueLimit) return `Queue full · ${input.queueUsed}/${input.queueLimit}`;
  if (input.queueUsed > 0) return 'Create another';
  return 'Create';
}

export function createStatusHint(input: {
  busy: boolean;
  coolingDown: boolean;
  cooldownSeconds: number;
  queueUsed: number;
  queueLimit: number;
}): string | null {
  if (input.queueUsed >= input.queueLimit) {
    return `Queue full (${input.queueUsed}/${input.queueLimit}). Wait until one song starts at Suno.`;
  }
  if (input.busy) {
    return 'Adding this song to the global queue. Paid songs go first.';
  }
  if (input.coolingDown && input.cooldownSeconds > 0) {
    return `You can create another in ${input.cooldownSeconds}s. No need to wait for audio.`;
  }
  if (input.queueUsed > 0) {
    return `${input.queueUsed} in the global queue. Suno starts them one by one.`;
  }
  return null;
}
