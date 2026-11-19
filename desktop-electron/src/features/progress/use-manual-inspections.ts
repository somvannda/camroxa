import { useCallback, useEffect, useRef, useState } from "react";
import { inspectRunDirectory, type ManualInspection } from "./manual-assets";
import { rowKey, stageKey } from "./progress-format";
import type { ProgressRow } from "./progress-types";

const MAX_AUTO_INSPECTIONS = 20;

/**
 * PG-34: inspect the run folders of rows that are waiting on manual images.
 * The probe reads the four expected file names through the files bridge, so a
 * file that exists but is unreadable reports as missing instead of throwing.
 */
export function useManualInspections(manualMode: boolean, rows: ProgressRow[]) {
  const [inspections, setInspections] = useState<Record<string, ManualInspection>>({});
  const [inspecting, setInspecting] = useState<Record<string, boolean>>({});
  const inFlight = useRef(new Set<string>());
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const inspectRow = useCallback(async (row: ProgressRow) => {
    const key = rowKey(row);
    if (inFlight.current.has(key)) return;
    inFlight.current.add(key);
    setInspecting((current) => ({ ...current, [key]: true }));
    try {
      const bridge = window.camxora?.files;
      const probe = async (path: string): Promise<boolean> => {
        if (!bridge) throw new Error("File access is unavailable in this window.");
        const result = await bridge.readImage(path);
        return result.ok;
      };
      const result = await inspectRunDirectory(row.meta.run_dir ?? "", probe);
      if (!mounted.current) return;
      setInspections((current) => ({ ...current, [key]: result }));
    } finally {
      inFlight.current.delete(key);
      if (mounted.current) {
        setInspecting((current) => {
          const next = { ...current };
          delete next[key];
          return next;
        });
      }
    }
  }, []);

  const imageSignature = rows
    .filter((row) => stageKey(row.stage) === "image" && Boolean(row.meta.run_dir))
    .slice(0, MAX_AUTO_INSPECTIONS)
    .map((row) => `${rowKey(row)}@${row.meta.run_dir ?? ""}`)
    .join("|");

  useEffect(() => {
    if (!manualMode) {
      setInspections({});
      return;
    }
    const targets = rows
      .filter((row) => stageKey(row.stage) === "image" && Boolean(row.meta.run_dir))
      .slice(0, MAX_AUTO_INSPECTIONS);
    for (const row of targets) void inspectRow(row);
    // Re-inspect only when the set of waiting run folders changes, not on every poll.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [manualMode, imageSignature, inspectRow]);

  const waitingKeys = new Set(
    Object.entries(inspections)
      .filter(([, inspection]) => !inspection.ready)
      .map(([key]) => key),
  );

  return { inspections, inspecting, inspectRow, waitingKeys };
}
