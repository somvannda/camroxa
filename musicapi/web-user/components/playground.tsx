"use client";

import { apiFetch, redirectToLogin } from "@/lib/api";
import { useEffect, useRef, useState } from "react";

export type JobStatus = "queued" | "running" | "streaming" | "complete" | "error";

export interface TaskResult {
  job_id: string;
  type?: string;
  status: JobStatus;
  result?: unknown;
  error?: string;
  clips?: Array<{
    id?: string;
    status?: string;
    title?: string;
    audio_url?: string;
    media_urls?: Array<{ url?: string; content_type?: string }>;
    prompt?: string;
    tags?: string;
    error_message?: string;
  }>;
}

export function clipAudio(clip: unknown): string | null {
  if (!clip || typeof clip !== "object") return null;
  const c = clip as { audio_url?: string; media_urls?: Array<{ url?: string; content_type?: string }> };
  const media = c.media_urls?.[0]?.url;
  if (media) return media;
  return c.audio_url || null;
}

export function clipDownloadUrl(clipId: string | number | undefined | null, format: "mp3" | "wav"): string {
  return `/backend/me/download?clip_id=${encodeURIComponent(String(clipId))}&format=${format}&force_download=1`;
}

export async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
  };
  let res: Response;
  try {
    // Session travels in the httpOnly cookie; send it on same-origin calls.
    res = await fetch(`/backend${path}`, { credentials: "same-origin", ...init, headers });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    if (e instanceof TypeError && /failed to fetch|networkerror|load failed/i.test(e.message)) {
      throw new Error("Cannot reach server. Check your connection or the backend service.");
    }
    throw new Error(e instanceof Error ? e.message : "Request failed");
  }
  if (res.status === 401) redirectToLogin();
  if (!res.ok) {
    if (res.status === 499) throw new DOMException("Aborted", "AbortError");
    const body = (await res.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error ?? `Request failed (${res.status})`);
  }
  return res;
}

const downloadClipLock = new Map<string, AbortController>();

export async function downloadClip(clipId: string | number | undefined | null, format: "mp3" | "wav"): Promise<void> {
  if (!clipId) return;
  const id = String(clipId);
  const lockKey = `${id}:${format}`;
  const prev = downloadClipLock.get(lockKey);
  if (prev) prev.abort();
  const ac = new AbortController();
  downloadClipLock.set(lockKey, ac);
  try {
    const res = await authorizedFetch(
      `/me/download?clip_id=${encodeURIComponent(id)}&format=${format}&force_download=1`,
      { method: "GET", signal: ac.signal },
    );
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const ext = format === "wav" ? "wav" : "mp3";
    const cd = res.headers.get("content-disposition");
    const match = cd?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
    a.download = match?.[1] ? decodeURIComponent(match[1].replace(/^UTF-8''/, "")) : `${id}.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 3000);
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") return;
    throw e;
  } finally {
    if (downloadClipLock.get(lockKey) === ac) downloadClipLock.delete(lockKey);
  }
}

export function AuthorizedAudio({ clipId, className }: { clipId: string; className?: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    let createdBlob: string | null = null;
    const ac = new AbortController();
    (async () => {
      try {
        setLoading(true);
        setErr(null);
        const res = await authorizedFetch(
          `/me/download?clip_id=${encodeURIComponent(clipId)}&format=mp3`,
          { method: "GET", signal: ac.signal },
        );
        const blob = await res.blob();
        createdBlob = URL.createObjectURL(blob);
        if (alive) setSrc(createdBlob);
      } catch (e) {
        if (!alive) return;
        if (e instanceof DOMException && e.name === "AbortError") return;
        const msg = e instanceof Error ? e.message : "Failed to load audio";
        const friendly = /cannot reach server|failed to fetch|networkerror|load failed/i.test(msg)
          ? "Audio not available — server unreachable."
          : /not available|expired|502/i.test(msg)
          ? "Audio not available. Clip may have expired."
          : msg;
        setErr(friendly);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
      ac.abort();
      if (createdBlob) URL.revokeObjectURL(createdBlob);
    };
  }, [clipId]);
  if (err) return <div className={`text-[11px] text-red-300 ${className ?? ""}`}>{err}</div>;
  if (loading) {
    return (
      <div className={`flex h-8 items-center gap-2 rounded-md bg-black/30 px-3 ${className ?? ""}`}>
        <svg viewBox="0 0 24 24" fill="none" className="h-3.5 w-3.5 animate-spin text-white/40">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4"/>
          <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="4" strokeLinecap="round"/>
        </svg>
        <span className="text-[11px] text-white/40">Loading audio…</span>
      </div>
    );
  }
  if (!src) return null;
  return (
    <audio
      controls
      preload="metadata"
      className={`w-full h-8 [&::-webkit-media-controls-panel]:bg-black/60 ${className ?? ""}`}
      src={src}
    >
      Your browser does not support the audio element.
    </audio>
  );
}

export interface UseJobOptions {
  onComplete?: (data: TaskResult) => void;
  intervalMs?: number;
  initialDelayMs?: number;
}

export interface UseJobState {
  busy: boolean;
  task: TaskResult | null;
  error: string;
  submit: (path: string, body: Record<string, unknown>) => Promise<void>;
  reset: () => void;
  retry: () => void;
  canRetry: boolean;
}

export function useJob(options: UseJobOptions = {}): UseJobState {
  const { onComplete, intervalMs = 3000, initialDelayMs = 1500 } = options;
  const [busy, setBusy] = useState(false);
  const [task, setTask] = useState<TaskResult | null>(null);
  const [error, setError] = useState("");
  const [lastSubmit, setLastSubmit] = useState<{ path: string; body: Record<string, unknown> } | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  function poll(jobId: string) {
    const tick = async () => {
      try {
        const data = await apiFetch<TaskResult>(`/me/task/${jobId}`);
        setTask(data);
        if (data.status === "complete") {
          setBusy(false);
          onComplete?.(data);
          return;
        }
        if (data.status === "error") {
          setBusy(false);
          setError(data.error || "Task failed");
          return;
        }
        pollRef.current = setTimeout(tick, intervalMs);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Polling failed");
        setBusy(false);
      }
    };
    pollRef.current = setTimeout(tick, initialDelayMs);
  }

  async function submit(path: string, body: Record<string, unknown>) {
    setLastSubmit({ path, body });
    setBusy(true);
    setError("");
    setTask(null);
    try {
      const created = await apiFetch<{ job_id: string; status: JobStatus }>(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
      poll(created.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setBusy(false);
    }
  }

  async function retry() {
    if (!lastSubmit) return;
    await submit(lastSubmit.path, lastSubmit.body);
  }

  function reset() {
    setTask(null);
    setError("");
    setBusy(false);
  }

  return { busy, task, error, submit, reset, retry, canRetry: lastSubmit != null };
}

export function PageShell(props: {
  title: string;
  subtitle: string;
  cardTitle?: string;
  cardSubtitle?: string;
  error?: string;
  children: React.ReactNode;
  output: React.ReactNode;
}) {
  return (
    <div className="pb-20">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">{props.title}</h1>
        <p className="mt-1 text-sm text-white/50">{props.subtitle}</p>
      </div>

      {props.error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {props.error}
        </div>
      )}

      <div className="space-y-6">
        <section className="rounded-2xl border border-white/5 bg-white/[0.02] p-6">
          {props.cardTitle && (
            <div className="mb-5">
              <h3 className="text-lg font-semibold text-white">{props.cardTitle}</h3>
              {props.cardSubtitle && <p className="mt-1 text-sm text-white/50">{props.cardSubtitle}</p>}
            </div>
          )}
          {props.children}
        </section>

        {props.output}
      </div>
    </div>
  );
}

export function Field(props: {
  label: string;
  required?: boolean;
  help?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 flex items-center gap-1 text-xs font-medium text-white/70">
        {props.label}
        {props.required && <span className="text-white/40">*</span>}
      </label>
      {props.children}
      {props.help && <p className="mt-1.5 text-xs text-white/40">{props.help}</p>}
    </div>
  );
}

export const inputCls =
  "w-full rounded-md border border-white/5 bg-black/30 px-3 py-2.5 text-sm text-white placeholder-white/25 outline-none transition focus:border-white/20 focus:bg-black/40";

export const textareaCls = `${inputCls} min-h-[96px] resize-y leading-relaxed`;

export function Switch({
  checked,
  onChange,
  label,
  labelFirst,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
  labelFirst?: boolean;
}) {
  const inner = (
    <span
      role="switch"
      aria-checked={checked}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onChange(!checked);
        }
      }}
      onClick={() => onChange(!checked)}
      className="flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border border-white/10 bg-white/5 p-0.5 transition-all hover:border-white/15"
    >
      <span
        className={`h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ${
          checked ? "translate-x-[18px]" : "translate-x-0"
        }`}
      />
    </span>
  );
  if (!label) return inner;
  if (labelFirst) {
    return (
      <div className="flex items-center gap-3">
        <span className="text-sm text-white/80">{label}</span>
        {inner}
      </div>
    );
  }
  return (
    <div className="flex items-center gap-3">
      {inner}
      <span className="text-sm text-white/80">{label}</span>
    </div>
  );
}

export function OutputTabs(props: {
  task: TaskResult | null;
  busy: boolean;
  readyTitle: string;
  readyBody: string;
  kind?: "clips" | "result";
  retry?: () => void;
  canRetry?: boolean;
  onReset?: () => void;
}) {
  const [tab, setTab] = useState<"overview" | "json">("overview");
  const { task, busy, readyTitle, readyBody, kind = "clips", retry, canRetry, onReset } = props;
  const terminal = task && (task.status === "complete" || task.status === "error");

  return (
    <section className="rounded-2xl border border-white/5 bg-white/[0.02]">
      <div className="flex items-center justify-between border-b border-white/5 px-5 py-3">
        <h3 className="text-sm font-semibold text-white/80">Output</h3>
        <div className="flex items-center gap-1 rounded-lg bg-black/30 p-0.5">
          {(["overview", "json"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-md px-3 py-1 text-xs font-medium capitalize transition ${
                tab === t ? "bg-white/10 text-white" : "text-white/50 hover:text-white/80"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <div className="p-5">
        {tab === "overview" ? (
          !task || (!busy && !terminal) ? (
            <div className="py-10 text-center">
              <div className="text-sm font-semibold text-white">{readyTitle}</div>
              <p className="mt-1 text-sm text-white/50">{readyBody}</p>
            </div>
          ) : busy && !terminal ? (
            <div className="space-y-4 py-8">
              <div className="mx-auto h-1.5 w-full max-w-md overflow-hidden rounded-full bg-white/5">
                <div className="h-full w-1/3 animate-[shimmer_1.4s_infinite] rounded-full bg-gradient-to-r from-transparent via-white/20 to-transparent" />
              </div>
              <p className="text-center text-sm text-white/50">Running… {task.status}</p>
            </div>
          ) : task.status === "error" ? (
            <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {task.error || "Failed"}
              <div className="mt-3 flex justify-end gap-2">
                {(canRetry !== undefined || retry !== undefined) && (
                  <button
                    className="rounded-md bg-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/15 disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={!canRetry || busy}
                    onClick={retry}
                  >
                    ↻ Retry
                  </button>
                )}
                {onReset !== undefined && (
                  <button
                    className="rounded-md px-3 py-1.5 text-xs font-medium text-white/60 hover:text-white/80 hover:bg-white/5 disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={onReset}
                  >
                    Dismiss
                  </button>
                )}
              </div>
            </div>
          ) : kind === "clips" ? (
            <ClipsOverview task={task} />
          ) : (
            <ResultOverview task={task} />
          )
        ) : (
          <pre className="max-h-[520px] overflow-auto rounded-lg bg-black/40 p-4 text-xs leading-relaxed text-white/80">
{JSON.stringify(task || { status: "not run" }, null, 2)}
          </pre>
        )}
      </div>
    </section>
  );
}

function ClipCard({ clip, index }: { clip: unknown; index: number }) {
  const [dlError, setDlError] = useState<string | null>(null);
  const obj = clip as Record<string, unknown>;
  const id = (obj.id ?? (obj as any).clip_id ?? `#${index + 1}`) as string;
  const title = (obj.title || (obj as any).task_id || id) as string;
  const clipError = (obj.error_message || obj.error) as string | undefined;

  const runDownload = async (format: "mp3" | "wav") => {
    try {
      setDlError(null);
      await downloadClip(id, format);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      const msg = e instanceof Error ? e.message : `${format.toUpperCase()} download failed`;
      setDlError(msg);
    }
  };

  return (
    <div className="rounded-xl border border-white/5 bg-black/20 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-white truncate max-w-[60ch]">{title}</div>
          <div className="mt-0.5 text-xs text-white/40">{id}</div>
        </div>
        {clipError && <span className="rounded-md bg-red-500/10 px-2 py-1 text-xs text-red-300">{clipError}</span>}
      </div>
      {dlError && (
        <div className="mt-3 rounded-md border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-300">{dlError}</div>
      )}
      {id && !id.startsWith("#") && (
        <div className="mt-4">
          <AuthorizedAudio clipId={id} />
        </div>
      )}
      {id && !id.startsWith("#") && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => { void runDownload("mp3"); }}
            className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/80 hover:bg-white/10 transition"
          >
            ⬇ Download MP3
          </button>
          <button
            type="button"
            onClick={() => { void runDownload("wav"); }}
            className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/80 hover:bg-white/10 transition"
          >
            ⬇ Download WAV
          </button>
        </div>
      )}
      {typeof obj.prompt === "string" && obj.prompt ? (
        <p className="mt-3 whitespace-pre-wrap text-xs text-white/55">{obj.prompt}</p>
      ) : null}
    </div>
  );
}

export function ClipsOverview({ task }: { task: TaskResult }) {
  const clips =
    Array.isArray(task.result) ? (task.result as unknown[])
    : Array.isArray((task.result as any)?.clips) ? (task.result as any).clips
    : Array.isArray((task.result as any)?.items) ? (task.result as any).items
    : task.result ? [task.result]
    : [];
  if (!clips.length) {
    return <p className="py-6 text-center text-sm text-white/50">No clips returned.</p>;
  }
  return (
    <div className="space-y-3">
      {clips.map((c: unknown, i: number) => (
        <ClipCard key={`${(c as Record<string, unknown>).id ?? i}-${i}`} clip={c} index={i} />
      ))}
    </div>
  );
}

export function ResultOverview({ task }: { task: TaskResult }) {
  const r = task.result;
  if (r == null) return <p className="py-6 text-center text-sm text-white/50">No result.</p>;
  if (typeof r === "object" && r && !Array.isArray(r)) {
    const entries = Object.entries(r as Record<string, unknown>);
    return (
      <dl className="divide-y divide-white/5 rounded-xl border border-white/5 bg-black/20">
        {entries.map(([k, v]) => (
          <div key={k} className="grid grid-cols-3 gap-3 px-4 py-3">
            <dt className="text-xs font-medium uppercase tracking-wide text-white/40">{k}</dt>
            <dd className="col-span-2 break-words text-sm text-white/85">
              {typeof v === "object" ? (
                <code className="block whitespace-pre-wrap rounded-md bg-black/40 p-2 text-xs text-white/70">
                  {JSON.stringify(v, null, 2)}
                </code>
              ) : (
                String(v)
              )}
            </dd>
          </div>
        ))}
      </dl>
    );
  }
  return (
    <pre className="whitespace-pre-wrap rounded-xl border border-white/5 bg-black/20 p-4 text-sm text-white/80">
{JSON.stringify(r, null, 2)}
    </pre>
  );
}

export function PrimaryButton(props: React.ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  const { busy, disabled, children, className = "", ...rest } = props;
  return (
    <button
      {...rest}
      disabled={busy || disabled}
      className={`w-full rounded-md bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-purple-500/20 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
    >
      {busy ? "Running…" : children}
    </button>
  );
}

export function ChoiceCard<T extends string>(props: {
  value: T;
  onChange: (v: T) => void;
  options: Array<{ key: T; title: string; description: string }>;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {props.options.map((o) => {
        const active = props.value === o.key;
        return (
          <button
            key={o.key}
            type="button"
            onClick={() => props.onChange(o.key)}
            className={`text-left rounded-xl border p-4 transition ${
              active
                ? "border-purple-400/40 bg-purple-500/10 shadow-md shadow-purple-500/10"
                : "border-white/5 bg-black/20 hover:border-white/15"
            }`}
          >
            <div className="text-sm font-semibold text-white">{o.title}</div>
            <p className="mt-1 text-xs text-white/50 leading-relaxed">{o.description}</p>
          </button>
        );
      })}
    </div>
  );
}
