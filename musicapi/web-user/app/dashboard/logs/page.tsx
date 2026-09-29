"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { AuthorizedAudio, downloadClip } from "@/components/playground";

interface DbLogRow {
  id: string;
  endpoint: string;
  model: string | null;
  prompt: string | null;
  status: string;
  credits_consumed: number;
  task_id: string | null;
  result_json: unknown;
  created_at: string;
}

type LogRow = {
  key: string;
  id: string;
  task_id: string | null;
  endpoint: string;
  model: string | null;
  prompt: string | null;
  status: string;
  credits: number;
  created_at: number;
  result_json: unknown;
  title?: string;
  style?: string;
  callback_url?: string;
};

const FILTER_TABS = [
  {
    key: "audio",
    label: "audio",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
        <path d="M9 18V5l12-2v13"/>
        <circle cx="6" cy="18" r="3"/>
        <circle cx="18" cy="16" r="3"/>
      </svg>
    ),
    match: (ep: string) => /^(generate|generate\/|gen_|music|audio)/i.test(ep) || /(generate|music|audio)$/i.test(ep),
  },
  {
    key: "recovery",
    label: "recovery",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
        <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
        <path d="M3 3v5h5"/>
      </svg>
    ),
    match: (ep: string) => /recovery/i.test(ep),
  },
  {
    key: "lyrics",
    label: "lyrics",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
        <path d="M4 6h16M4 12h16M4 18h10"/>
      </svg>
    ),
    match: (ep: string) => /lyric/i.test(ep),
  },
  {
    key: "subtitle",
    label: "subtitle",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
        <rect width="20" height="16" x="2" y="4" rx="2"/>
        <path d="M6 16h4M14 16h4M6 12h12"/>
      </svg>
    ),
    match: (ep: string) => /subtitle|caption|srt|vtt/i.test(ep),
  },
  {
    key: "wav",
    label: "wav",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
        <path d="M4 12v3a3 3 0 0 0 3 3h0a3 3 0 0 0 3-3V9a3 3 0 0 1 3-3h0a3 3 0 0 1 3 3v6a3 3 0 0 0 3 3h0a3 3 0 0 0 3-3v-3"/>
      </svg>
    ),
    match: (ep: string) => /wav|convert.*wav/i.test(ep),
  },
  {
    key: "vocal-removal",
    label: "vocal-removal",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="22"/>
        <line x1="2" y1="2" x2="22" y2="22"/>
      </svg>
    ),
    match: (ep: string) => /vocal.*remov|separate|stems?|split/i.test(ep),
  },
  {
    key: "video",
    label: "video",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
        <rect width="20" height="16" x="2" y="4" rx="2"/>
        <path d="m10 11 5 3-5 3z"/>
      </svg>
    ),
    match: (ep: string) => /video/i.test(ep),
  },
  {
    key: "voice",
    label: "voice",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="22"/>
      </svg>
    ),
    match: (ep: string) => /voice|clone.*persona|persona|check.*voice|generate.*voice/i.test(ep),
  },
];

function statusChip(status: string): React.ReactNode {
  const s = (status || "").toLowerCase();
  if (s === "complete" || s === "success") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-md border border-[var(--emerald)]/30 bg-[var(--emerald)]/10 px-2.5 py-1 text-[11px] font-bold tracking-wider text-[var(--emerald)]">
        SUCCESS
      </span>
    );
  }
  if (s === "error" || s === "failed") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-md border border-red-500/25 bg-red-500/10 px-2.5 py-1 text-[11px] font-bold tracking-wider text-red-300">
        FAILED
      </span>
    );
  }
  if (s === "running" || s === "streaming" || s === "queued") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-md border border-indigo-500/25 bg-indigo-500/10 px-2.5 py-1 text-[11px] font-bold tracking-wider text-indigo-300">
        RUNNING
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-semibold tracking-wider text-white/60">
      {s.toUpperCase() || "PENDING"}
    </span>
  );
}

function formatDate(ms: number): string {
  try {
    const d = new Date(ms);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch {
    return "";
  }
}

function safeParseResult(r: unknown): unknown {
  if (typeof r === "string") {
    try { return JSON.parse(r); } catch { return r; }
  }
  return r;
}

function extractClipIds(result: unknown): string[] {
  if (!result) return [];
  if (Array.isArray(result)) {
    return result.map((c) => (c as Record<string, unknown>)?.id as string).filter(Boolean);
  }
  if (typeof result !== "object") return [];
  const rec = result as Record<string, unknown>;
  const candidates: unknown[] = [];
  if (Array.isArray(rec.clips)) candidates.push(...rec.clips);
  if (Array.isArray(rec.items)) candidates.push(...rec.items);
  if (Array.isArray(rec.data)) candidates.push(...rec.data);
  return candidates.map((c) => (c as Record<string, unknown>)?.id as string).filter(Boolean);
}

function firstClip(result: unknown): Record<string, unknown> | null {
  if (!result) return null;
  if (Array.isArray(result)) {
    const c = result[0];
    return c && typeof c === "object" ? (c as Record<string, unknown>) : null;
  }
  if (typeof result !== "object") return null;
  const rec = result as Record<string, unknown>;
  const list = Array.isArray(rec.clips) ? rec.clips : Array.isArray(rec.items) ? rec.items : [];
  const c = list[0];
  return c && typeof c === "object" ? (c as Record<string, unknown>) : null;
}

/** Cover art the provider attached to the generated clip, if any. */
function extractCover(result: unknown): string | null {
  const rec = result && typeof result === "object" && !Array.isArray(result) ? (result as Record<string, unknown>) : null;
  const clip = firstClip(result);
  const candidates = [
    clip?.image_url, clip?.image_large_url, clip?.cover_url, clip?.imageUrl,
    rec?.image_url, rec?.cover_url,
  ];
  for (const c of candidates) {
    if (typeof c === "string" && c.trim()) return c;
  }
  return null;
}

function extractPromptFields(prompt: string | null, result: unknown): { title?: string; style?: string; promptText?: string; callback_url?: string } {
  const out: { title?: string; style?: string; promptText?: string; callback_url?: string } = {};
  if (result && typeof result === "object") {
    const rec = result as Record<string, unknown>;
    if (typeof rec.callback_url === "string") out.callback_url = rec.callback_url;
    if (typeof rec.callbackUrl === "string") out.callback_url = rec.callbackUrl;
    const fc = firstClip(result);
    if (fc) {
      if (typeof fc.title === "string") out.title = fc.title;
      if (typeof fc.style === "string") out.style = fc.style;
    }
  }
  if (prompt && typeof prompt === "string") {
    try {
      const obj = JSON.parse(prompt);
      if (typeof obj === "object" && obj) {
        if (!out.title && typeof obj.title === "string") out.title = obj.title;
        if (!out.style && typeof obj.style === "string") out.style = obj.style;
        if (!out.callback_url && typeof obj.callback_url === "string") out.callback_url = obj.callback_url;
        if (!out.callback_url && typeof obj.callbackUrl === "string") out.callback_url = obj.callbackUrl;
        if (typeof obj.prompt === "string") out.promptText = obj.prompt;
        if (typeof obj.lyrics === "string" && !out.promptText) out.promptText = obj.lyrics;
      }
    } catch {
      out.promptText = prompt;
    }
  }
  if (!out.promptText && typeof prompt === "string") out.promptText = prompt;
  return out;
}

/** Lyrics attached to the clip / result / request payload. */
function extractLyrics(row: LogRow): string | null {
  const result = row.result_json;
  if (result && typeof result === "object" && !Array.isArray(result)) {
    const rec = result as Record<string, unknown>;
    if (typeof rec.lyrics === "string" && rec.lyrics.trim()) return rec.lyrics;
    const clip = firstClip(result);
    if (clip && typeof clip.lyrics === "string" && clip.lyrics.trim()) return clip.lyrics;
  }
  if (row.prompt) {
    try {
      const obj = JSON.parse(row.prompt);
      if (obj && typeof obj === "object" && typeof obj.lyrics === "string" && obj.lyrics.trim()) return obj.lyrics;
    } catch {
      /* prompt is plain text */
    }
  }
  return null;
}

export default function LogsPage() {
  const [rows, setRows] = useState<LogRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [taskIdSearch, setTaskIdSearch] = useState("");
  const [activeTab, setActiveTab] = useState("audio");
  const [resultModal, setResultModal] = useState<{ row: LogRow; clipIds: string[] } | null>(null);

  const loadLive = useCallback(async () => {
    try {
      const live = await apiFetch<Array<{ job_id: string; type: string; status: string; endpoint?: string; prompt?: string; model?: string; credits?: number; created_at?: number }>>("/me/jobs/running");
      const now = Date.now();
      return live.map<LogRow>((j) => ({
        key: `live-${j.job_id}`,
        id: j.job_id,
        task_id: j.job_id,
        endpoint: j.endpoint || j.type || "unknown",
        model: j.model || null,
        prompt: j.prompt || null,
        status: j.status || "pending",
        credits: j.credits ?? 0,
        created_at: j.created_at || now,
        result_json: null,
      }));
    } catch {
      return [] as LogRow[];
    }
  }, []);

  const load = useCallback(async () => {
    try {
      setError("");
      const [db, live] = await Promise.all([
        apiFetch<DbLogRow[]>("/me/logs").catch(() => [] as DbLogRow[]),
        loadLive(),
      ]);
      const mapped: LogRow[] = db.map((d) => {
        const result = safeParseResult(d.result_json);
        const fields = extractPromptFields(d.prompt, result);
        return {
          key: `db-${d.id}`,
          id: d.id,
          task_id: d.task_id,
          endpoint: d.endpoint || "unknown",
          model: d.model,
          prompt: d.prompt,
          status: d.status,
          credits: d.credits_consumed,
          created_at: new Date(d.created_at).getTime(),
          result_json: result,
          title: fields.title,
          style: fields.style,
          callback_url: fields.callback_url,
        };
      });
      const seen = new Set(mapped.map((r) => r.task_id).filter(Boolean) as string[]);
      const merged = [
        ...live.filter((r) => !seen.has(r.task_id as string)),
        ...mapped,
      ].sort((a, b) => b.created_at - a.created_at);
      setRows(merged);
      return merged.filter((r) => ["pending", "running", "streaming", "queued"].includes((r.status || "").toLowerCase())).length;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load logs");
      return 0;
    }
  }, [loadLive]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const tick = async () => {
      const liveCount = await load();
      if (!cancelled) setLoading(false);
      if (!cancelled && liveCount > 0) {
        timer = setTimeout(tick, 5000);
      }
    };
    (async () => {
      setLoading(true);
      await tick();
    })();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [load]);

  const filtered = useMemo(() => {
    let out = rows;
    if (taskIdSearch.trim()) {
      const q = taskIdSearch.trim().toLowerCase();
      out = out.filter((r) => (r.task_id || "").toLowerCase().includes(q) || (r.id || "").toLowerCase().includes(q));
    }
    if (activeTab) {
      const tab = FILTER_TABS.find((t) => t.key === activeTab);
      if (tab) out = out.filter((r) => tab.match(r.endpoint));
    }
    return out;
  }, [rows, taskIdSearch, activeTab]);

  const showError = (msg: string) => {
    setError(msg);
    window.setTimeout(() => setError(""), 6000);
  };

  return (
    <div className="pb-20">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Logs</h1>
          <p className="mt-1 text-sm text-white/50">An overview of your latest requests</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-white/40">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.3-4.3"/>
            </svg>
            <input
              type="text"
              value={taskIdSearch}
              onChange={(e) => setTaskIdSearch(e.target.value)}
              placeholder="Enter taskId"
              className="h-9 w-64 rounded-lg border border-white/10 bg-white/[0.03] pl-9 pr-3 text-xs text-white placeholder:text-white/35 focus:border-white/20 focus:bg-white/[0.05] focus:outline-none"
            />
          </div>
          <button
            type="button"
            onClick={() => { setLoading(true); void load().finally(() => setLoading(false)); }}
            disabled={loading}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 text-xs font-medium text-white/80 transition hover:bg-white/10 disabled:opacity-60"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {FILTER_TABS.map((t) => {
          const active = activeTab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveTab(active ? "" : t.key)}
              className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-medium transition ${
                active
                  ? "border-white/15 bg-white/10 text-white shadow-sm"
                  : "border-white/5 bg-white/[0.02] text-white/45 hover:border-white/10 hover:bg-white/[0.04] hover:text-white/70"
              }`}
            >
              <span className={active ? "text-white/80" : "text-white/30"}>{t.icon}</span>
              {t.label}
            </button>
          );
        })}
      </div>

      {error && <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}

      <div className="overflow-hidden rounded-xl border border-white/5 bg-white/[0.02]">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[1100px]">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-white/35 border-b border-white/5 bg-white/[0.015]">
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Model</th>
                <th className="px-4 py-3 font-medium">Prompt</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Credits</th>
                <th className="px-4 py-3 font-medium">taskId</th>
                <th className="px-4 py-3 font-medium">Actions</th>
                <th className="px-4 py-3 font-medium text-right">Result</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                const clipIds = extractClipIds(r.result_json);
                const st = (r.status || "").toLowerCase();
                const isComplete = st === "complete" || st === "success";
                const canDownload = clipIds.length > 0 && isComplete;
                return (
                  <tr key={r.key} className="border-b border-white/[0.035] transition hover:bg-white/[0.015] last:border-b-0">
                    <td className="px-4 py-3.5 text-white/55 whitespace-nowrap text-xs tabular-nums align-top">
                      {formatDate(r.created_at)}
                    </td>
                    <td className="px-4 py-3.5 text-white/80 font-medium whitespace-nowrap text-xs align-top">
                      {r.endpoint}
                    </td>
                    <td className="px-4 py-3.5 text-white/70 whitespace-nowrap text-xs align-top">
                      {r.model || <span className="text-white/25">—</span>}
                    </td>
                    <td className="px-4 py-3.5 align-top max-w-[420px]">
                      <PromptCard row={r} />
                    </td>
                    <td className="px-4 py-3.5 align-top">{statusChip(r.status)}</td>
                    <td className="px-4 py-3.5 text-white/80 tabular-nums text-xs align-top">{r.credits}</td>
                    <td className="px-4 py-3.5 font-mono text-[11px] text-white/55 whitespace-nowrap align-top">
                      {r.task_id ? r.task_id : <span className="text-white/25">—</span>}
                    </td>
                    <td className="px-4 py-3.5 align-top">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <DownloadButton format="mp3" clipId={clipIds[0]} enabled={canDownload} onError={showError} />
                        <DownloadButton format="wav" clipId={clipIds[0]} enabled={canDownload} onError={showError} />
                        {!canDownload && clipIds.length === 0 && <span className="text-[10px] text-white/20">no clip</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 align-top">
                      <div className="flex justify-end">
                        <ResultCell row={r} clipIds={clipIds} canOpen={canDownload} onOpen={() => setResultModal({ row: r, clipIds })} />
                      </div>
                    </td>
                  </tr>
                );
              })}
              {loading && filtered.length === 0 && (
                <tr><td colSpan={9} className="px-4 py-14 text-center text-xs text-white/35">Loading…</td></tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={9} className="px-4 py-14 text-center text-xs text-white/40">No requests found for this filter.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {resultModal && (
        <ResultModal
          clipIds={resultModal.clipIds}
          row={resultModal.row}
          onClose={() => setResultModal(null)}
          onError={showError}
        />
      )}
    </div>
  );
}

function PromptCard({ row }: { row: LogRow }) {
  const fields = extractPromptFields(row.prompt, row.result_json);
  const promptText = fields.promptText || row.prompt || "";
  const callback = fields.callback_url || row.callback_url;
  const hasAny = !!(fields.title || fields.style || promptText || callback);
  if (!hasAny) return <span className="text-xs text-white/25">—</span>;
  return (
    <div className="rounded-lg border border-white/5 bg-black/30 p-2.5">
      <div className="space-y-1 text-[11px] leading-relaxed">
        {fields.title && (
          <div className="truncate text-white/75">
            <span className="font-semibold text-white/50">title: </span>
            <span title={fields.title}>{fields.title}</span>
          </div>
        )}
        {fields.style && (
          <div className="truncate text-white/70">
            <span className="font-semibold text-white/45">style: </span>
            <span title={fields.style}>{fields.style}</span>
          </div>
        )}
        {promptText && (
          <div className="line-clamp-2 text-white/65" title={promptText}>
            <span className="font-semibold text-white/40">prompt: </span>
            {promptText}
          </div>
        )}
        {callback && (
          <div className="flex items-start gap-1 pt-0.5">
            <span className="shrink-0 font-semibold text-white/35 whitespace-nowrap">callbackUrl: </span>
            <span className="min-w-0 flex-1 truncate text-white/50 underline decoration-dotted underline-offset-2" title={callback}>
              {callback}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function DownloadButton({ format, clipId, enabled, onError }: { format: "mp3" | "wav"; clipId?: string; enabled: boolean; onError: (msg: string) => void }) {
  const tone = format === "mp3"
    ? "border-[var(--emerald)]/20 bg-[var(--emerald)]/10 text-[var(--emerald)] hover:bg-[var(--emerald)]/20"
    : "border-indigo-500/20 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20";
  return (
    <button
      type="button"
      aria-disabled={!enabled}
      onClick={() => {
        if (!enabled || !clipId) return;
        void downloadClip(clipId, format).catch((e) => {
          if (e instanceof DOMException && e.name === "AbortError") return;
          onError(e?.message ?? `${format.toUpperCase()} download failed`);
        });
      }}
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium transition ${
        enabled ? tone : "border-white/5 bg-white/[0.015] text-white/20 pointer-events-none cursor-not-allowed"
      }`}
    >
      {format.toUpperCase()}
    </button>
  );
}

/** Result cell: hover reveals a preview card (cover image, lyrics, download); click opens playback. */
function ResultCell({ row, clipIds, canOpen, onOpen }: { row: LogRow; clipIds: string[]; canOpen: boolean; onOpen: () => void }) {
  const cover = extractCover(row.result_json);
  const lyrics = extractLyrics(row);
  const initials = (row.title || row.endpoint || "?").trim().charAt(0).toUpperCase() || "?";
  return (
    <div className="group relative">
      <button
        type="button"
        disabled={!canOpen}
        onClick={() => canOpen && onOpen()}
        className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[11px] font-medium transition ${
          canOpen
            ? "border-white/10 bg-white/[0.04] text-white/80 hover:bg-white/[0.08] hover:text-white"
            : "border-white/5 bg-white/[0.015] text-white/25 cursor-not-allowed"
        }`}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
          <path d="M9 18V5l12-2v13"/>
          <circle cx="6" cy="18" r="3"/>
          <circle cx="18" cy="16" r="3"/>
        </svg>
        Result
      </button>
      {canOpen && (
        <div className="pointer-events-none absolute right-0 top-full z-30 mt-1 hidden w-72 rounded-xl border border-white/10 bg-[#1a1a1d] p-3 shadow-2xl group-hover:block">
          {cover ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={cover} alt="" className="mb-2 h-36 w-full rounded-lg object-cover" />
          ) : (
            <div className="mb-2 flex h-24 w-full items-center justify-center rounded-lg border border-white/10 bg-gradient-to-br from-violet-500/20 to-fuchsia-500/10 text-2xl font-bold text-white/50">
              {initials}
            </div>
          )}
          {lyrics ? (
            <p className="line-clamp-6 whitespace-pre-wrap text-[11px] leading-relaxed text-white/60">{lyrics}</p>
          ) : (
            <p className="text-[11px] text-white/35">No lyrics for this request.</p>
          )}
          <button
            type="button"
            onClick={() => { void downloadClip(clipIds[0], "mp3").catch(() => {}); }}
            className="pointer-events-auto mt-2.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] font-medium text-white/80 transition hover:bg-white/10"
          >
            Download MP3
          </button>
        </div>
      )}
    </div>
  );
}

function ResultModal({ clipIds, row, onClose, onError }: { clipIds: string[]; row: LogRow; onClose: () => void; onError?: (msg: string) => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-2xl rounded-2xl border border-white/10 bg-[#141416] p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-white">Result — {row.endpoint}</h3>
            <p className="mt-0.5 text-xs text-white/45">taskId: {row.task_id || row.id} · {formatDate(row.created_at)}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-white/50 transition hover:bg-white/5 hover:text-white"
            aria-label="Close"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div className="space-y-3">
          {clipIds.length === 0 && (
            <div className="rounded-lg border border-white/5 bg-black/30 p-4 text-xs text-white/50">
              No downloadable audio clips found for this request.
            </div>
          )}
          {clipIds.map((id) => (
            <div key={id} className="rounded-lg border border-white/5 bg-black/30 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="font-mono text-[11px] text-white/55">{id}</span>
                <div className="flex items-center gap-1.5">
                  <DownloadButton format="mp3" clipId={id} enabled onError={(m) => onError?.(m)} />
                  <DownloadButton format="wav" clipId={id} enabled onError={(m) => onError?.(m)} />
                </div>
              </div>
              <AuthorizedAudio clipId={id} />
            </div>
          ))}
        </div>

        {row.result_json != null && (
          <details className="mt-4 rounded-lg border border-white/5 bg-black/30 p-3">
            <summary className="cursor-pointer text-[11px] font-medium text-white/55 hover:text-white/75">Raw Response JSON</summary>
            <pre className="mt-3 max-h-[260px] overflow-auto text-[11px] leading-relaxed text-white/60 whitespace-pre-wrap">
              {JSON.stringify(row.result_json, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
