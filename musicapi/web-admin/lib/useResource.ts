"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface ResourceState<T> {
  data: T | null;
  error: string;
  loading: boolean;
  /** Re-run the fetcher, showing the loading state. Safe to call from handlers. */
  reload: () => Promise<T | null>;
  /** Update the cached data locally (e.g. optimistic edits). */
  setData: (value: T | null | ((prev: T | null) => T | null)) => void;
}

/**
 * Fetch-on-mount + manual reload without writing state synchronously inside an
 * effect (which React 19's `react-hooks/set-state-in-effect` flags). State is
 * only written from promise callbacks, so this is safe in effects and strict
 * mode. Re-fetching is controlled by `deps`; the fetcher itself is held in a
 * ref so an inline arrow function doesn't restart the effect every render.
 */
export function useResource<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList = [],
): ResourceState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);

  // Always call the latest fetcher, without making it an effect dependency.
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    let active = true;
    fetcherRef
      .current()
      .then((result) => {
        if (!active) return;
        setData(result);
        setError("");
      })
      .catch((e: unknown) => {
        if (!active) return;
        setError(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // Callers drive refetching through `deps`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  const reload = useCallback(async (): Promise<T | null> => {
    setLoading(true);
    setError("");
    try {
      const result = await fetcherRef.current();
      setData(result);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const setDataSafe = useCallback(
    (value: T | null | ((prev: T | null) => T | null)) => {
      setData((prev) =>
        typeof value === "function" ? (value as (p: T | null) => T | null)(prev) : value,
      );
    },
    [],
  );

  return { data, error, loading, reload, setData: setDataSafe };
}
