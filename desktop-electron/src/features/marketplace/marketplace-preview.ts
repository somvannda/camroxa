const MAX_CONCURRENT_PREVIEWS = 4;
const previewCache = new Map<string, string>();
const failedUntil = new Map<string, number>();

let active = 0;
const waiting: Array<() => void> = [];

function withSlot<T>(task: () => Promise<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const start = () => {
      active += 1;
      task()
        .then(resolve, reject)
        .finally(() => {
          active -= 1;
          waiting.shift()?.();
        });
    };
    if (active < MAX_CONCURRENT_PREVIEWS) start();
    else waiting.push(start);
  });
}

/**
 * Marketplace previews are fetched in the main process (the session token never
 * reaches the renderer) and returned as data URLs. Cards share a small cache and
 * a four-at-a-time concurrency cap.
 */
export async function loadPreview(itemId: string, previewUrl: string): Promise<string> {
  const key = `${itemId}\n${previewUrl}`;
  const cached = previewCache.get(key);
  if (cached) return cached;
  const retryAt = failedUntil.get(key);
  if (retryAt && retryAt > Date.now()) {
    throw new Error("Preview unavailable.");
  }

  const url = await withSlot(() => window.camxora.templates.preview({ itemId, url: previewUrl }));
  if (!url.ok) {
    failedUntil.set(key, Date.now() + 30_000);
    throw new Error(url.error.message || "Preview unavailable.");
  }
  previewCache.set(key, url.data.dataUrl);
  return url.data.dataUrl;
}

export function clearPreviewCache(): void {
  previewCache.clear();
  failedUntil.clear();
}
