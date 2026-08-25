/** Drop a failed native src so the element can become a silent hold or idle. */

export function clearNativeMediaSrc(media: HTMLMediaElement) {
  try {
    media.pause();
  } catch {
    /* ignore */
  }
  try {
    media.removeAttribute('src');
    media.load();
  } catch {
    /* ignore */
  }
}
