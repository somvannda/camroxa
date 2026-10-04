"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { AuthorizedAudio, downloadClip } from "@/components/playground";
import {
  buildMidiFile,
  classifyResult,
  downloadBytes,
  type Artifact,
  type TextAsset,
} from "@/lib/artifacts";

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
    label: "recovery audio",
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
    label: "lyrics video generator",
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

// Endpoint substrings sent to GET /me/logs/page for each tab.
const TAB_PATTERNS: Record<string, string[]> = {
  audio: ["music", "generate", "audio"],
  recovery: ["recovery"],
  lyrics: ["lyric"],
  subtitle: ["subtitle", "caption", "srt", "vtt"],
  wav: ["wav"],
  "vocal-removal": ["vocal", "stem", "separate", "split"],
  video: ["video"],
  voice: ["voice", "persona"],
};

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

type DateKey = "today" | "7d" | "30d" | "3m" | "all";

function dateWindow(key: DateKey): { start?: string; end?: string } {
  if (key === "all") return {};
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const today = new Date();
  const end = iso(today);
  if (key === "today") return { start: end, end };
  const days = key === "7d" ? 7 : key === "30d" ? 30 : 90;
  const s = new Date(today);
  s.setDate(s.getDate() - (days - 1));
  return { start: iso(s), end };
}

export default function LogsPage() {
  const [rows, setRows] = useState<LogRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState("");
  const [taskIdSearch, setTaskIdSearch] = useState("");
  const [activeTab, setActiveTab] = useState("audio");
  const [resultModal, setResultModal] = useState<LogRow | null>(null);
  const [dateKey, setDateKey] = useState<DateKey>("30d");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { start, end } = dateWindow(dateKey);
      const patterns = TAB_PATTERNS[activeTab] ?? [];
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (start) params.set("start", start);
      if (end) params.set("end", end);
      if (patterns.length) params.set("endpoint", patterns.join(","));
      if (taskIdSearch.trim()) params.set("task_id", taskIdSearch.trim());
      const res = await apiFetch<{ rows: DbLogRow[]; total: number; page: number; pages: number }>(
        `/me/logs/page?${params.toString()}`,
      );
      const mapped: LogRow[] = res.rows.map((d) => {
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
      setRows(mapped);
      setTotal(res.total);
      setPages(res.pages);
      if (res.page !== page) setPage(res.page);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load logs");
    } finally {
      setLoading(false);
    }
  }, [dateKey, activeTab, page, pageSize, taskIdSearch]);

  useEffect(() => {
    queueMicrotask(() => {
      void load();
    });
  }, [load]);

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
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={dateKey}
            onChange={(e) => { setDateKey(e.target.value as typeof dateKey); setPage(1); }}
            className="h-9 rounded-lg border border-white/10 bg-white/[0.03] px-3 text-xs text-white/80 outline-none focus:border-white/20"
          >
            <option value="today" className="bg-[#141416]">Today</option>
            <option value="7d" className="bg-[#141416]">Last 7 days</option>
            <option value="30d" className="bg-[#141416]">Last 30 days</option>
            <option value="3m" className="bg-[#141416]">Last 3 months</option>
            <option value="all" className="bg-[#141416]">All time</option>
          </select>
          <div className="relative">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-white/40">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.3-4.3"/>
            </svg>
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { setTaskIdSearch(searchInput); setPage(1); } }}
              placeholder="Enter taskId"
              className="h-9 w-56 rounded-lg border border-white/10 bg-white/[0.03] pl-9 pr-8 text-xs text-white placeholder:text-white/35 focus:border-white/20 focus:bg-white/[0.05] focus:outline-none"
            />
            {searchInput && (
              <button
                type="button"
                onClick={() => { setSearchInput(""); setTaskIdSearch(""); setPage(1); }}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-white/40 hover:text-white"
              >
                ×
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => { setPage(1); void load(); }}
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
              onClick={() => { setActiveTab(t.key); setPage(1); }}
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
              {rows.map((r) => {
                const artifact = classifyResult(r.result_json, r.endpoint);
                const st = (r.status || "").toLowerCase();
                const isComplete = st === "complete" || st === "success";
                const hasResult = r.result_json != null;
                const canAct = isComplete && artifact.kind !== "raw";
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
                      <ArtifactActions artifact={artifact} enabled={canAct} onError={showError} />
                    </td>
                    <td className="px-4 py-3.5 align-top">
                      <div className="flex justify-end">
                        <ResultCell row={r} artifact={artifact} canOpen={hasResult} onOpen={() => setResultModal(r)} />
                      </div>
                    </td>
                  </tr>
                );
              })}
              {loading && rows.length === 0 && (
                <tr><td colSpan={9} className="px-4 py-14 text-center text-xs text-white/35">Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={9} className="px-4 py-14 text-center text-xs text-white/40">No logs found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-white/50">
        <div className="flex items-center gap-2">
          Rows per page
          <select
            value={pageSize}
            onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
            className="h-8 rounded-lg border border-white/10 bg-white/[0.03] px-2 text-xs text-white/80 outline-none focus:border-white/20"
          >
            {[10, 20, 50].map((n) => (
              <option key={n} value={n} className="bg-[#141416]">{n}</option>
            ))}
          </select>
          <span className="ml-2">{total} logs</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || loading}
            className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white/80 transition hover:bg-white/10 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="tabular-nums">{page} / {pages}</span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page >= pages || loading}
            className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white/80 transition hover:bg-white/10 disabled:opacity-40"
          >
            Next
          </button>
          <span className="ml-2 inline-flex items-center gap-1">
            Go to
            <input
              type="number"
              min={1}
              max={pages}
              value={page}
              onChange={(e) => { const v = Number(e.target.value); if (v >= 1 && v <= pages) setPage(v); }}
              className="h-8 w-14 rounded-md border border-white/10 bg-white/[0.03] px-2 text-center text-xs text-white outline-none focus:border-white/20"
            />
            page
          </span>
        </div>
      </div>

      {resultModal && (
        <ResultModal
          row={resultModal}
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

type ButtonTone = "neutral" | "mp3" | "wav" | "mp4" | "midi" | "text";

const BUTTON_TONES: Record<ButtonTone, string> = {
  neutral: "border-white/10 bg-white/[0.04] text-white/75 hover:bg-white/10",
  mp3: "border-[var(--emerald)]/20 bg-[var(--emerald)]/10 text-[var(--emerald)] hover:bg-[var(--emerald)]/20",
  wav: "border-indigo-500/20 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20",
  mp4: "border-sky-500/20 bg-sky-500/10 text-sky-300 hover:bg-sky-500/20",
  midi: "border-fuchsia-500/20 bg-fuchsia-500/10 text-fuchsia-300 hover:bg-fuchsia-500/20",
  text: "border-amber-500/20 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20",
};

function MiniButton({ label, title, enabled = true, tone = "neutral", onClick }: {
  label: string;
  title?: string;
  enabled?: boolean;
  tone?: ButtonTone;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-disabled={!enabled}
      onClick={() => { if (enabled) onClick(); }}
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium transition ${
        enabled ? BUTTON_TONES[tone] : "border-white/5 bg-white/[0.015] text-white/20 pointer-events-none cursor-not-allowed"
      }`}
    >
      {label}
    </button>
  );
}

function DownloadButton({ format, clipId, enabled, onError }: { format: "mp3" | "wav" | "mp4"; clipId?: string | null; enabled: boolean; onError: (msg: string) => void }) {
  return (
    <MiniButton
      label={format.toUpperCase()}
      tone={format}
      enabled={enabled && !!clipId}
      onClick={() => {
        void downloadClip(clipId, format).catch((e) => {
          if (e instanceof DOMException && e.name === "AbortError") return;
          onError(e?.message ?? `${format.toUpperCase()} download failed`);
        });
      }}
    />
  );
}

/**
 * Render the correct export actions for a result artifact: MP3/WAV for audio,
 * MP4 for videos, a generated `.mid` for MIDI transcriptions, and LRC/SRT/TXT
 * for lyric/subtitle text. Nothing is downloadable for a persona.
 */
function ArtifactActions({ artifact, enabled, onError }: { artifact: Artifact; enabled: boolean; onError: (msg: string) => void }) {
  switch (artifact.kind) {
    case "audio": {
      const clipId = artifact.clips[0]?.id;
      return (
        <div className="flex flex-wrap items-center gap-1.5">
          <DownloadButton format="mp3" clipId={clipId} enabled={enabled} onError={onError} />
          <DownloadButton format="wav" clipId={clipId} enabled={enabled} onError={onError} />
        </div>
      );
    }
    case "video":
      return <DownloadButton format="mp4" clipId={artifact.clipId} enabled={enabled} onError={onError} />;
    case "midi":
      return (
        <MiniButton
          label="MID"
          tone="midi"
          title="Download Standard MIDI File"
          enabled={enabled}
          onClick={() => downloadBytes("transcription.mid", buildMidiFile(artifact.instruments), "audio/midi")}
        />
      );
    case "text":
      return (
        <div className="flex flex-wrap items-center gap-1.5">
          {artifact.assets.map((a) => (
            <MiniButton key={a.label} label={a.label} tone="text" title={`Download ${a.filename}`} enabled={enabled}
              onClick={() => downloadBytes(a.filename, a.content, a.mime)} />
          ))}
        </div>
      );
    case "image":
      return <MiniButton label="IMG" title="Open cover image" enabled={enabled}
        onClick={() => window.open(artifact.imageUrl, "_blank", "noopener")} />;
    case "persona":
      return <span className="text-[10px] text-white/30">persona</span>;
    default:
      return <span className="text-[10px] text-white/20">no media</span>;
  }
}

function artifactSummary(artifact: Artifact): string {
  switch (artifact.kind) {
    case "video": return "Music video (MP4)";
    case "midi": return `${artifact.instruments.length} instrument${artifact.instruments.length === 1 ? "" : "s"} transcribed`;
    case "text": return artifact.assets.map((a) => a.label).join(" · ");
    case "persona": return "Voice persona";
    case "image": return "Cover image";
    case "raw": return "Raw response";
    case "audio": return "";
  }
}

/** The single most useful export for the hover preview card. */
function primaryDownload(artifact: Artifact): { label: string; run: () => void } | null {
  switch (artifact.kind) {
    case "audio": {
      const id = artifact.clips[0]?.id;
      return id ? { label: "Download MP3", run: () => { void downloadClip(id, "mp3").catch(() => {}); } } : null;
    }
    case "video":
      return artifact.clipId ? { label: "Download MP4", run: () => { void downloadClip(artifact.clipId, "mp4").catch(() => {}); } } : null;
    case "midi":
      return { label: "Download MID", run: () => downloadBytes("transcription.mid", buildMidiFile(artifact.instruments), "audio/midi") };
    case "text": {
      const a = artifact.assets[0];
      return a ? { label: `Download ${a.label}`, run: () => downloadBytes(a.filename, a.content, a.mime) } : null;
    }
    case "image":
      return { label: "Open image", run: () => window.open(artifact.imageUrl, "_blank", "noopener") };
    default:
      return null;
  }
}

/** Result cell: hover reveals a preview card (cover image, lyrics, download); click opens the artifact. */
function ResultCell({ row, artifact, canOpen, onOpen }: { row: LogRow; artifact: Artifact; canOpen: boolean; onOpen: () => void }) {
  const cover = artifact.kind === "audio" ? extractCover(row.result_json) : artifact.kind === "image" ? artifact.imageUrl : null;
  const lyrics = artifact.kind === "audio" || artifact.kind === "text" ? extractLyrics(row) : null;
  const summary = artifactSummary(artifact);
  const primary = primaryDownload(artifact);
  const initials = (row.title || row.endpoint || "?").trim().charAt(0).toUpperCase() || "?";
  const btnRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  // The table lives in an overflow container, so an absolutely-positioned card
  // gets clipped. Render the preview with fixed coordinates instead, flipped up
  // when there isn't room below the button.
  function show() {
    const r = btnRef.current?.getBoundingClientRect();
    if (!r) return;
    const width = 288;
    const left = Math.min(Math.max(8, r.right - width), window.innerWidth - width - 8);
    const below = r.bottom + 8;
    const top = below + 280 > window.innerHeight ? Math.max(8, r.top - 288) : below;
    setPos({ top, left });
  }
  function hide() {
    setPos(null);
  }
  useEffect(() => {
    if (!pos) return;
    const onScrollResize = () => setPos(null);
    window.addEventListener("scroll", onScrollResize, true);
    window.addEventListener("resize", onScrollResize);
    return () => {
      window.removeEventListener("scroll", onScrollResize, true);
      window.removeEventListener("resize", onScrollResize);
    };
  }, [pos]);

  return (
    <div className="relative">
      <button
        ref={btnRef}
        type="button"
        disabled={!canOpen}
        onMouseEnter={() => canOpen && show()}
        onMouseLeave={hide}
        onFocus={() => canOpen && show()}
        onBlur={hide}
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
      {canOpen && pos && (
        <div
          onMouseEnter={show}
          onMouseLeave={hide}
          style={{ position: "fixed", top: pos.top, left: pos.left, width: 288 }}
          className="z-[60] rounded-xl border border-white/10 bg-[#1a1a1d] p-3 shadow-2xl"
        >
          {cover ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={cover} alt="" className="mb-2 h-36 w-full rounded-lg object-cover" />
          ) : (
            <div className="mb-2 flex h-24 w-full items-center justify-center rounded-lg border border-white/10 bg-gradient-to-br from-violet-500/20 to-fuchsia-500/10 text-2xl font-bold text-white/50">
              {initials}
            </div>
          )}
          {summary ? (
            <p className="text-[11px] text-white/70">{summary}</p>
          ) : lyrics ? (
            <p className="line-clamp-6 whitespace-pre-wrap text-[11px] leading-relaxed text-white/60">{lyrics}</p>
          ) : (
            <p className="text-[11px] text-white/35">No lyrics for this request.</p>
          )}
          {primary && (
            <button
              type="button"
              onClick={primary.run}
              className="mt-2.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] font-medium text-white/80 transition hover:bg-white/10"
            >
              {primary.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function TextAssetCard({ asset, onError }: { asset: TextAsset; onError?: (msg: string) => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="rounded-lg border border-white/5 bg-black/30 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold text-white/60">{asset.label}</span>
        <div className="flex items-center gap-1.5">
          <MiniButton
            label={copied ? "Copied" : "Copy"}
            onClick={() => {
              void navigator.clipboard
                ?.writeText(asset.content)
                .then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500); })
                .catch(() => onError?.("Copy failed"));
            }}
          />
          <MiniButton label={`Download ${asset.label}`} tone="text" onClick={() => downloadBytes(asset.filename, asset.content, asset.mime)} />
        </div>
      </div>
      <pre className="max-h-[260px] overflow-auto whitespace-pre-wrap text-[11px] leading-relaxed text-white/60">{asset.content}</pre>
    </div>
  );
}

function ResultModal({ row, onClose, onError }: { row: LogRow; onClose: () => void; onError?: (msg: string) => void }) {
  const artifact = classifyResult(row.result_json, row.endpoint);

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
          {artifact.kind === "audio" && (artifact.clips.length === 0 ? (
            <div className="rounded-lg border border-white/5 bg-black/30 p-4 text-xs text-white/50">
              No downloadable audio clips found for this request.
            </div>
          ) : artifact.clips.map(({ id, audioUrl }) => (
            <div key={id} className="rounded-lg border border-white/5 bg-black/30 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="font-mono text-[11px] text-white/55">{id}</span>
                <div className="flex items-center gap-1.5">
                  <DownloadButton format="mp3" clipId={id} enabled onError={(m) => onError?.(m)} />
                  <DownloadButton format="wav" clipId={id} enabled onError={(m) => onError?.(m)} />
                </div>
              </div>
              <AuthorizedAudio clipId={id} src={audioUrl} />
            </div>
          )))}

          {artifact.kind === "video" && (
            <div className="rounded-lg border border-white/5 bg-black/30 p-3">
              {artifact.videoUrl ? (
                <video controls src={artifact.videoUrl} className="w-full rounded-lg border border-white/5 bg-black" />
              ) : (
                <div className="text-xs text-white/50">The video is not directly previewable. Use the MP4 download.</div>
              )}
              {artifact.clipId && (
                <div className="mt-2 flex justify-end">
                  <DownloadButton format="mp4" clipId={artifact.clipId} enabled onError={(m) => onError?.(m)} />
                </div>
              )}
            </div>
          )}

          {artifact.kind === "midi" && (
            <div className="rounded-lg border border-white/5 bg-black/30 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-[11px] text-white/55">
                  {artifact.instruments.length} instrument{artifact.instruments.length === 1 ? "" : "s"} ·{" "}
                  {artifact.instruments.reduce((n, inst) => n + inst.notes.length, 0)} notes
                </span>
                <MiniButton label="Download MID" tone="midi"
                  onClick={() => downloadBytes("transcription.mid", buildMidiFile(artifact.instruments), "audio/midi")} />
              </div>
              <div className="space-y-1.5">
                {artifact.instruments.map((inst, i) => (
                  <div key={`${inst.name}-${i}`} className="flex items-center justify-between rounded-md border border-white/5 bg-white/[0.02] px-2.5 py-1.5 text-[11px]">
                    <span className="truncate text-white/75">{inst.name}</span>
                    <span className="text-white/40">{inst.notes.length} notes</span>
                  </div>
                ))}
                {artifact.instruments.length === 0 && (
                  <div className="text-xs text-white/45">No instruments were transcribed.</div>
                )}
              </div>
            </div>
          )}

          {artifact.kind === "text" && artifact.assets.map((asset) => (
            <TextAssetCard key={asset.label} asset={asset} onError={onError} />
          ))}

          {artifact.kind === "persona" && (
            <div className="rounded-lg border border-white/5 bg-black/30 p-3">
              <p className="mb-2 text-xs text-white/50">This request created a voice persona — there is no downloadable audio.</p>
              {artifact.fields.length > 0 && (
                <div className="space-y-1.5">
                  {artifact.fields.map((f) => (
                    <div key={f.label} className="flex items-center justify-between gap-3 text-[11px]">
                      <span className="font-medium text-white/45">{f.label}</span>
                      <span className="min-w-0 flex-1 truncate text-right text-white/75" title={f.value}>{f.value}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {artifact.kind === "image" && (
            <div className="rounded-lg border border-white/5 bg-black/30 p-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={artifact.imageUrl} alt="" className="max-h-[360px] w-full rounded-lg object-contain" />
            </div>
          )}

          {artifact.kind === "raw" && (
            <div className="rounded-lg border border-white/5 bg-black/30 p-4 text-xs text-white/50">
              No playable media for this request. See the raw response below.
            </div>
          )}
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
