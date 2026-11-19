import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  YoutubeAvailability,
  YoutubeChannelSummary,
  YoutubeUploadPlan,
  YoutubeUploadState,
} from "../../../electron/shared/types";
import {
  availabilityFor,
  availabilitySignature,
  latestUploadFor,
  uploadCandidateRows,
  uploadRowQuery,
} from "./youtube-upload-format";
import type { ProgressRow } from "./progress-types";

export interface UploadConfirmation {
  row: ProgressRow;
  plan: YoutubeUploadPlan;
  /** `profile` (default), `none`, or a playlist id. */
  playlist: string;
  retryJobUid: string | null;
  pickPlaylist: boolean;
}

export interface YoutubeUploadController {
  availability: YoutubeAvailability | null;
  availabilityError: string | null;
  active: YoutubeUploadState | null;
  history: YoutubeUploadState[];
  rowState: (key: string) => ReturnType<typeof availabilityFor>;
  uploadFor: (key: string) => YoutubeUploadState | undefined;
  channelFor: (profileId: string | null | undefined) => YoutubeChannelSummary | null;
  confirmation: UploadConfirmation | null;
  preparing: boolean;
  starting: boolean;
  actionError: string | null;
  refresh: () => Promise<void>;
  openConfirm: (row: ProgressRow, options?: { playlist?: string; retry?: boolean; pickPlaylist?: boolean }) => Promise<void>;
  setPlaylist: (playlist: string) => void;
  closeConfirm: () => void;
  confirmUpload: () => Promise<void>;
  cancelUpload: () => Promise<void>;
  clearActionError: () => void;
}

/**
 * Manual YouTube upload state for the Progress page.
 *
 * Readiness comes from the main process (merged file, channel, quota, legacy
 * template). Nothing here starts on its own: `openConfirm` only builds the
 * confirmation, and `confirmUpload` is the sole call that begins a transfer.
 */
export function useYoutubeUpload(rows: ProgressRow[]): YoutubeUploadController {
  const [availability, setAvailability] = useState<YoutubeAvailability | null>(null);
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);
  const [active, setActive] = useState<YoutubeUploadState | null>(null);
  const [history, setHistory] = useState<YoutubeUploadState[]>([]);
  const [confirmation, setConfirmation] = useState<UploadConfirmation | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    void window.camxora.youtube.state().then((result) => {
      if (!alive || !result.ok) return;
      setActive(result.data.active);
      setHistory(result.data.history);
    });
    const unsubscribe = window.camxora.youtube.onChange((payload) => {
      if (!alive) return;
      const upload = payload.upload;
      setHistory((current) =>
        [upload, ...current.filter((item) => item.uploadId !== upload.uploadId)].slice(0, 20),
      );
      setActive(upload.finishedAt ? null : upload);
      if (upload.finishedAt) setRefreshTick((tick) => tick + 1);
    });
    return () => {
      alive = false;
      unsubscribe();
    };
  }, []);

  const signature = useMemo(() => availabilitySignature(rows), [rows]);
  const queries = useMemo(
    () =>
      uploadCandidateRows(rows)
        .map((row) => uploadRowQuery(row))
        .filter((item): item is NonNullable<ReturnType<typeof uploadRowQuery>> => Boolean(item)),
    [rows],
  );
  const queriesRef = useRef(queries);
  queriesRef.current = queries;

  const refresh = useCallback(async () => {
    const list = queriesRef.current;
    if (list.length === 0) {
      setAvailability(null);
      setAvailabilityError(null);
      return;
    }
    const result = await window.camxora.youtube.availability({ rows: list });
    if (!mounted.current) return;
    if (!result.ok) {
      setAvailabilityError(result.error.message);
      return;
    }
    setAvailability(result.data);
    setAvailabilityError(null);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, signature, refreshTick]);

  const openConfirm = useCallback(
    async (
      row: ProgressRow,
      options?: { playlist?: string; retry?: boolean; pickPlaylist?: boolean },
    ) => {
      const query = uploadRowQuery(row);
      if (!query) {
        setActionError("This row has no batch id or channel profile to upload.");
        return;
      }
      setPreparing(true);
      setActionError(null);
      try {
        const result = await window.camxora.youtube.plan({ row: query });
        if (!mounted.current) return;
        if (!result.ok) {
          setActionError(result.error.message);
          return;
        }
        const key = query.key;
        const previous = history.find((item) => item.key === key && item.phase === "failed");
        setConfirmation({
          row,
          plan: result.data,
          playlist: options?.playlist ?? "profile",
          retryJobUid: options?.retry ? (previous?.jobUid ?? null) : null,
          pickPlaylist: options?.pickPlaylist === true,
        });
      } catch (error) {
        if (mounted.current) {
          setActionError(error instanceof Error ? error.message : "Unable to prepare the upload.");
        }
      } finally {
        if (mounted.current) setPreparing(false);
      }
    },
    [history],
  );

  const setPlaylist = useCallback((playlist: string) => {
    setConfirmation((current) => (current ? { ...current, playlist } : current));
  }, []);

  const closeConfirm = useCallback(() => {
    setConfirmation(null);
    setActionError(null);
  }, []);

  const confirmUpload = useCallback(async () => {
    if (!confirmation) return;
    const query = uploadRowQuery(confirmation.row);
    if (!query) {
      setActionError("This row has no batch id or channel profile to upload.");
      return;
    }
    setStarting(true);
    setActionError(null);
    try {
      const result = await window.camxora.youtube.start({
        key: query.key,
        batchId: query.batchId,
        profileId: query.profileId,
        role: query.role,
        runDir: query.runDir,
        playlist: confirmation.playlist,
        retryJobUid: confirmation.retryJobUid,
      });
      if (!mounted.current) return;
      if (!result.ok) {
        setActionError(result.error.message);
        return;
      }
      setActive(result.data);
      setConfirmation(null);
    } catch (error) {
      if (mounted.current) {
        setActionError(error instanceof Error ? error.message : "Unable to start the upload.");
      }
    } finally {
      if (mounted.current) setStarting(false);
    }
  }, [confirmation]);

  const cancelUpload = useCallback(async () => {
    try {
      await window.camxora.youtube.cancel(active?.uploadId);
    } catch (error) {
      if (mounted.current) {
        setActionError(error instanceof Error ? error.message : "Unable to cancel the upload.");
      }
    }
  }, [active]);

  const clearActionError = useCallback(() => setActionError(null), []);

  const rowState = useCallback(
    (key: string) => availabilityFor(availability, key),
    [availability],
  );

  const uploadFor = useCallback(
    (key: string) => latestUploadFor(active ? [active, ...history] : history, key),
    [active, history],
  );

  const channelFor = useCallback(
    (profileId: string | null | undefined) => {
      if (!profileId) return availability?.channel ?? null;
      return availability?.channels.find((item) => item.profileId === profileId) ?? null;
    },
    [availability],
  );

  return {
    availability,
    availabilityError,
    active,
    history,
    rowState,
    uploadFor,
    channelFor,
    confirmation,
    preparing,
    starting,
    actionError,
    refresh,
    openConfirm,
    setPlaylist,
    closeConfirm,
    confirmUpload,
    cancelUpload,
    clearActionError,
  };
}
