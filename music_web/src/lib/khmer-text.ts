/** Khmer letters, digits, and symbols (Unicode blocks). */
const KHMER_RE = /[\u1780-\u17FF\u19E0-\u19FF]/;

export function containsKhmer(text: string | null | undefined): boolean {
  return Boolean(text && KHMER_RE.test(text));
}

/** Apply when copy includes Khmer so Siemreap shapes clusters without Latin tracking. */
export function khmerTextClass(text: string | null | undefined): string {
  return containsKhmer(text) ? 'font-khmer' : '';
}
