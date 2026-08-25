/** MediaError.code 4 = MEDIA_ERR_SRC_NOT_SUPPORTED (iOS Chrome HLS miss / bad src). */

export function isUnsupportedSrcError(err: unknown, media?: HTMLMediaElement | null): boolean {
  if (typeof MediaError !== 'undefined' && err instanceof MediaError) {
    return err.code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED;
  }
  if (media?.error?.code === 4) return true;
  const name = err instanceof Error ? err.name : '';
  const text =
    err instanceof Error
      ? err.message
      : typeof MediaError !== 'undefined' && err instanceof MediaError
        ? err.message || `Media error ${err.code}`
        : String(err || '');
  if (name === 'NotSupportedError') return true;
  if (err && typeof err === 'object' && 'code' in err && Number((err as { code: unknown }).code) === 4) {
    return true;
  }
  return /media error 4|media_err_src_not_supported|no supported source|format is not supported|native media load failed|native media playback failed|native play timeout/i.test(
    text,
  );
}

export function iosChromeFriendlyError(err: unknown, media?: HTMLMediaElement | null): string {
  if (isUnsupportedSrcError(err, media)) {
    return 'Tap play again to start audio.';
  }
  const text = err instanceof Error ? err.message : String(err || '');
  return text.trim() || 'Tap play again to start audio.';
}
