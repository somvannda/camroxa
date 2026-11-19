import { useCallback, useEffect, useState } from "react";
import type { VizzyRenderSummary } from "../../../electron/shared/types";

export interface VizzyRendersHandle {
  items: VizzyRenderSummary[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  remove: (name: string) => Promise<void>;
  reveal: (name: string) => Promise<void>;
  /** Opaque `camxora-media://` URL for inline playback. */
  play: (name: string) => Promise<string | null>;
}

/** Managed `renders/` files, listed through the shell-only IPC surface. */
export function useVizzyRenders(open: boolean): VizzyRendersHandle {
  const [items, setItems] = useState<VizzyRenderSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await window.camxora.vizzy.renders();
      if (response.ok) {
        setItems(response.data);
        setError(null);
      } else {
        setError(response.error.message);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not list renders.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void refresh();
  }, [open, refresh]);

  const remove = useCallback(
    async (name: string) => {
      const response = await window.camxora.vizzy.deleteRender(name);
      if (!response.ok) {
        setError(response.error.message);
        return;
      }
      if (!response.data.deleted) setError("That render was already gone.");
      await refresh();
    },
    [refresh],
  );

  const reveal = useCallback(async (name: string) => {
    const response = await window.camxora.vizzy.revealRender(name);
    if (!response.ok) setError(response.error.message);
  }, []);

  const play = useCallback(async (name: string) => {
    const response = await window.camxora.vizzy.renderUrl(name);
    if (!response.ok) {
      setError(response.error.message);
      return null;
    }
    return response.data.url;
  }, []);

  return { items, loading, error, refresh, remove, reveal, play };
}
