'use client';

import { useState, type ReactNode } from 'react';

/**
 * Cover art that never renders a broken-image icon.
 *
 * Web-music covers are stored as raw Suno CDN URLs, which can be blocked by
 * hotlink protection (a Referer from our origin) or expire over time. Rendering
 * those with a plain <img> left blank/broken art with no way to recover. This
 * wrapper:
 *   - sends no Referer, so hotlink-protected CDN hosts serve the image, and
 *   - falls back to caller-supplied content when the image fails, and
 *   - retries automatically when `src` changes (e.g. a refreshed URL appears).
 */
export function CoverImage({
  src,
  alt = '',
  className,
  fallback,
}: {
  src?: string | null;
  alt?: string;
  className?: string;
  fallback: ReactNode;
}) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const resolved = typeof src === 'string' ? src.trim() : '';

  if (!resolved || failedSrc === resolved) {
    return <>{fallback}</>;
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={resolved}
      alt={alt}
      className={className}
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailedSrc(resolved)}
    />
  );
}
