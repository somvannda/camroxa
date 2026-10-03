"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

/** A result clip plus its best inline CDN URL, for direct streaming playback. */
interface LogClip {
  id: string;
  audioUrl: string | null;
}

function extractClipList(result: unknown): LogClip[] {
  let list: unknown[] = [];
  if (Array.isArray(result)) {
    list = result;
  } else if (result && typeof result === "object") {
    const rec = result as Record<string, unknown>;
    if (Array.isArray(rec.clips)) list.push(...rec.clips);
    if (Array.isArray(rec.items)) list.push(...rec.items);
    if (Array.isArray(rec.data)) list.push(...rec.data);
  }
  const out: LogClip[] = [];
  for (const c of list) {
    if (!c || typeof c !== "object") continue;
    const rec = c as { id?: unknown; audio_url?: unknown; media_urls?: Array<{ url?: unknown }> };
    if (typeof rec.id !== "string" || !rec.id) continue;
    const media = Array.isArray(rec.media_urls) ? rec.media_urls[0]?.url : null;
    const audioUrl = typeof media === "string" ? media : typeof rec.audio_url === "string" ? rec.audio_url : null;
    out.push({ id: rec.id, audioUrl });
  }
  return out;
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
  const [resultModal, setResultModal] = useState<{ row: LogRow; clips: LogClip[] } | null>(null);
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
                const clips = extractClipList(r.result_json);
                const clipIds = clips.map((c) => c.id);
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
                        <ResultCell row={r} clipIds={clipIds} canOpen={canDownload} onOpen={() => setResultModal({ row: r, clips })} />
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
          clips={resultModal.clips}
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
          {lyrics ? (
            <p className="line-clamp-6 whitespace-pre-wrap text-[11px] leading-relaxed text-white/60">{lyrics}</p>
          ) : (
            <p className="text-[11px] text-white/35">No lyrics for this request.</p>
          )}
          <button
            type="button"
            onClick={() => { void downloadClip(clipIds[0], "mp3").catch(() => {}); }}
            className="mt-2.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] font-medium text-white/80 transition hover:bg-white/10"
          >
            Download MP3
          </button>
        </div>
      )}
    </div>
  );
}

function ResultModal({ clips, row, onClose, onError }: { clips: LogClip[]; row: LogRow; onClose: () => void; onError?: (msg: string) => void }) {
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
          {clips.length === 0 && (
            <div className="rounded-lg border border-white/5 bg-black/30 p-4 text-xs text-white/50">
              No downloadable audio clips found for this request.
            </div>
          )}
          {clips.map(({ id, audioUrl }) => (
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
