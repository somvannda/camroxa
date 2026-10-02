"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import {
  addDays,
  MAX_RANGE_DAYS,
  rangeDays,
  todayISO,
  type UsageRange,
} from "./date-range-picker";

/**
 * Export dialog mirroring sunoapi.org's `/usage` export: pick a range (default
 * last 31 days), download a CSV of `Model, Credits Consumed, Create Time, Task ID`.
 */

interface LogRow {
  endpoint?: string | null;
  model?: string | null;
  credits_consumed?: number | null;
  task_id?: string | null;
  created_at: string;
}

function csvCell(value: unknown): string {
  const s = value == null ? "" : String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function defaultExportRange(): UsageRange {
  const end = todayISO();
  return { start: addDays(end, -30), end };
}

export function ExportDialog({ onClose }: { onClose: () => void }) {
  const [start, setStart] = useState(() => defaultExportRange().start);
  const [end, setEnd] = useState(() => defaultExportRange().end);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !busy) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const invalidOrder = !!start && !!end && end < start;
  const days = start && end ? rangeDays({ start, end }) : 0;
  const exceeds = !!start && !!end && !invalidOrder && days > MAX_RANGE_DAYS;
  const valid = !!start && !!end && !invalidOrder && !exceeds;

  async function doExport() {
    if (!valid) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const rows = await apiFetch<LogRow[]>(`/me/logs?start=${start}&end=${end}&limit=5000`);
      if (!rows.length) {
        setError("No data to export");
        return;
      }
      const header = ["Model", "Credits Consumed", "Create Time", "Task ID"];
      const lines = [header.map(csvCell).join(",")];
      const sorted = [...rows].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      );
      for (const row of sorted) {
        lines.push(
          [
            row.model || row.endpoint || "",
            String(row.credits_consumed ?? 0),
            formatDateTime(row.created_at),
            row.task_id || "",
          ]
            .map(csvCell)
            .join(","),
        );
      }
      const blob = new Blob([`\uFEFF${lines.join("\n")}`], { type: "text/csv;charset=utf-8;" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `usage_data_${start}_to_${end}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      setMessage("Usage data exported successfully");
      // Match sunoapi.org: dismiss the dialog once the download starts.
      window.setTimeout(onClose, 800);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to export usage data. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => !busy && onClose()}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-md rounded-2xl border border-white/10 bg-[#141416] p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-col gap-1">
          <div className="text-xl font-semibold text-white">Export</div>
          <p className="text-sm text-white/50">Export Usage Data</p>
        </div>

        <div className="mt-5 space-y-4">
          <div>
            <label className="mb-1 block text-xs text-white/50">Start time</label>
            <input
              type="date"
              value={start}
              max={todayISO()}
              onChange={(e) => setStart(e.target.value)}
              className="w-full rounded-md border border-white/10 bg-white/[0.03] px-2 py-2 text-sm text-white outline-none [color-scheme:dark] focus:border-white/25"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-white/50">End time</label>
            <input
              type="date"
              value={end}
              min={start || undefined}
              max={todayISO()}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full rounded-md border border-white/10 bg-white/[0.03] px-2 py-2 text-sm text-white outline-none [color-scheme:dark] focus:border-white/25"
            />
          </div>

          {(exceeds || invalidOrder) && (
            <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-300">
              {invalidOrder && <div>• Start date must be before end date</div>}
              {exceeds && <div>• Date range cannot exceed {MAX_RANGE_DAYS} days</div>}
            </div>
          )}

          {valid && (
            <div className="rounded-lg bg-emerald-500/10 p-3 text-sm text-emerald-300">
              ✓ Selected {days} days data
            </div>
          )}

          {busy && (
            <div className="space-y-2">
              <div className="text-sm text-white/60">Preparing export...</div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                <div className="h-full w-2/3 animate-pulse rounded-full bg-[#3b82f6]" />
              </div>
            </div>
          )}

          {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}
          {message && <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">{message}</div>}
        </div>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg px-3 py-2 text-sm font-medium text-white/70 transition hover:bg-white/[0.05] hover:text-white disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void doExport()}
            disabled={!valid || busy}
            className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Exporting..." : "Export"}
          </button>
        </div>
      </div>
    </div>
  );
}
