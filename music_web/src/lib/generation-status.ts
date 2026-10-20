/**
 * Suno generation statuses, mirrored from
 * platform_api/services/suno_status_messages.SUNO_FAILURE_STATUSES.
 *
 * Suno reports a failure under many statuses. All of them are terminal: a song
 * in one of these states must render as failed (with its delete action) instead
 * of looking like it is still generating and polling forever.
 */

export const TERMINAL_FAILURE_STATUSES: ReadonlySet<string> = new Set([
  'FAILED',
  'REJECTED',
  'ERROR',
  'FAILURE',
  'CANCELLED',
  'CANCELED',
  'SENSITIVE_WORD_ERROR',
  'CREATE_TASK_FAILED',
  'GENERATE_AUDIO_FAILED',
  'CALLBACK_EXCEPTION',
  'GENERATE_LYRICS_FAILED',
  'SENSITIVE_CONTENT',
  'CONTENT_POLICY',
  'POLICY_VIOLATION',
]);

export function isFailedStatus(status: string | null | undefined): boolean {
  return TERMINAL_FAILURE_STATUSES.has((status || '').trim().toUpperCase());
}
