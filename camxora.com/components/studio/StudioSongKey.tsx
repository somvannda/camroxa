"use client";

import { useEffect, useState } from "react";

import { computeKey, type EstimatedKey } from "@/lib/studio-key";

/**
 * Key tag for a library song row (§19.2). The reference shows a key; our payload has none,
 * so it is estimated from the audio and prefixed with “≈” to stay honest about that.
 * Renders nothing when the chroma is flat (a near-tie between relative keys).
 */

const cache = new Map<string, EstimatedKey | null>();

export function SongKey({ url }: { url?: string | null }) {
  const [key, setKey] = useState<EstimatedKey | null>(() => (url ? cache.get(url) ?? null : null));

  useEffect(() => {
    if (!url) return;
    if (cache.has(url)) {
      setKey(cache.get(url) ?? null);
      return;
    }
    let cancelled = false;
    void computeKey(url).then((result) => {
      cache.set(url, result);
      if (!cancelled) setKey(result);
    });
    return () => {
      cancelled = true;
    };
  }, [url]);

  if (!key) return null;
  return (
    <span title="Estimated from the audio, not provider metadata">
      ≈ {key.tonic} {key.mode}
    </span>
  );
}
