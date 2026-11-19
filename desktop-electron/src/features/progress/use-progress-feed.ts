import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiRequest, errorMessage } from "../../lib/api";
import {
  PROGRESS_ACTIVE_POLL_MS,
  PROGRESS_POLL_MS,
  progressQuery,
  rangeError,
  prepareRows,
} from "./progress-format";
import { PollController } from "./progress-poll";
import type { ProgressListResponse, ProgressRow, ProgressSettings } from "./progress-types";

/**
 * Progress rows only. Music downloads are owned by the main-process coordinator
 * (see `use-download-queue`), so this feed no longer fetches the pending list:
 * the shell is the single reader of `/music/downloads/pending`.
 */
export interface ProgressFeedOptions {
  from: string;
  to: string;
  activeOnly: boolean;
  limit: number;
}

export interface ProgressFeed {
  data: ProgressListResponse | null;
  rows: ProgressRow[];
  settings: ProgressSettings | null;
  settingsError: string | null;
  error: string | null;
  rangeMessage: string | null;
  loading: boolean;
  busy: boolean;
  lastLoadedAt: number | null;
  refresh: () => Promise<void>;
}

async function fetchProgress(options: ProgressFeedOptions): Promise<ProgressListResponse> {
  const query = progressQuery(options.from, options.to, options.limit, options.activeOnly);
  const response = await apiRequest<ProgressListResponse>({
    method: "GET",
    path: "/progress",
    query,
  });
  return {
    ...response,
    rows: Array.isArray(response.rows) ? response.rows : [],
  };
}

export function useProgressFeed(options: ProgressFeedOptions): ProgressFeed {
  const [data, setData] = useState<ProgressListResponse | null>(null);
  const [settings, setSettings] = useState<ProgressSettings | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [inflight, setInflight] = useState(0);
  const [lastLoadedAt, setLastLoadedAt] = useState<number | null>(null);

  const mounted = useRef(true);
  const loadSequence = useRef(0);
  const filtersRef = useRef(options);
  filtersRef.current = options;
  const activeOnlyRef = useRef(options.activeOnly);
  activeOnlyRef.current = options.activeOnly;
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const progressController = useRef<PollController | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const loadProgress = useCallback(async () => {
    const current = filtersRef.current;
    if (rangeError(current.from, current.to)) return;
    const sequence = loadSequence.current + 1;
    loadSequence.current = sequence;
    setInflight((count) => count + 1);
    try {
      const response = await fetchProgress(current);
      if (!mounted.current || sequence !== loadSequence.current) return;
      setData(response);
      setError(null);
      setLastLoadedAt(Date.now());
    } catch (loadError) {
      if (!mounted.current || sequence !== loadSequence.current) return;
      setError(errorMessage(loadError));
    } finally {
      if (mounted.current) {
        setInflight((count) => Math.max(0, count - 1));
        setLoading(false);
      }
    }
  }, []);

  const loadSettings = useCallback(async () => {
    try {
      const response = await apiRequest<ProgressSettings>({ method: "GET", path: "/settings" });
      if (!mounted.current) return;
      setSettings(response ?? {});
      setSettingsError(null);
    } catch (loadError) {
      if (!mounted.current) return;
      setSettingsError(errorMessage(loadError));
    }
  }, []);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    const controller = new PollController({
      poll: loadProgress,
      intervalMs: () =>
        activeOnlyRef.current ? PROGRESS_ACTIVE_POLL_MS : PROGRESS_POLL_MS,
    });
    progressController.current = controller;
    if (!document.hidden) controller.start();
    return () => {
      controller.stop();
      if (progressController.current === controller) progressController.current = null;
    };
  }, [loadProgress, options.from, options.to, options.activeOnly, options.limit]);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.hidden) {
        progressController.current?.stop();
        return;
      }
      progressController.current?.start();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  const refresh = useCallback(async () => {
    const tasks: Array<Promise<void>> = [];
    if (progressController.current) tasks.push(progressController.current.trigger());
    if (!settingsRef.current) tasks.push(loadSettings());
    await Promise.all(tasks);
  }, [loadSettings]);

  const rows = useMemo(() => prepareRows(data?.rows ?? []), [data?.rows]);

  return {
    data,
    rows,
    settings,
    settingsError,
    error,
    rangeMessage: rangeError(options.from, options.to),
    loading,
    busy: inflight > 0,
    lastLoadedAt,
    refresh,
  };
}
