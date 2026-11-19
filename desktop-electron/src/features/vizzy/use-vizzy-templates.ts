import { useCallback, useEffect, useRef, useState } from "react";
import type { VideoTemplateInfo, VizzyOpenResult } from "../../../electron/shared/types";

export interface VizzyTemplatesHandle {
  items: VideoTemplateInfo[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  remove: (id: string) => Promise<boolean>;
  preview: (id: string) => Promise<VizzyOpenResult | null>;
  openLibrary: () => Promise<boolean>;
}

/**
 * Saved video templates, listed through the shell-only `video-templates:*`
 * surface. A save or delete anywhere in the app emits `video-templates:changed`,
 * which refreshes this list without polling.
 */
export function useVizzyTemplates(open: boolean): VizzyTemplatesHandle {
  const [items, setItems] = useState<VideoTemplateInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const openRef = useRef(open);
  openRef.current = open;

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await window.camxora.videoTemplates.list();
      if (response.ok) {
        setItems(response.data);
        setError(null);
      } else {
        setError(response.error.message);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not list video templates.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const subscribe = window.camxora?.videoTemplates?.onChange;
    if (!subscribe) return;
    return subscribe(() => {
      if (openRef.current) void refresh();
    });
  }, [refresh]);

  useEffect(() => {
    if (open) void refresh();
  }, [open, refresh]);

  const remove = useCallback(
    async (id: string) => {
      const response = await window.camxora.videoTemplates.remove(id);
      if (!response.ok) {
        setError(response.error.message);
        return false;
      }
      if (!response.data) {
        setError("That template was already gone.");
        await refresh();
        return false;
      }
      await refresh();
      return true;
    },
    [refresh],
  );

  const preview = useCallback(async (id: string) => {
    const response = await window.camxora.vizzy.previewTemplate(id);
    if (!response.ok) {
      setError(response.error.message);
      return null;
    }
    return response.data;
  }, []);

  const openLibrary = useCallback(async () => {
    const response = await window.camxora.vizzy.openLibrary();
    if (!response.ok) {
      setError(response.error.message);
      return false;
    }
    return response.data.opened;
  }, []);

  return { items, loading, error, refresh, remove, preview, openLibrary };
}
