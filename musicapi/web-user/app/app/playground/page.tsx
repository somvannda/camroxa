"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

const VERSIONS = [
  { label: "v4.5-all", key: "chirp-auk-turbo" },
  { label: "v4", key: "chirp-v4" },
  { label: "v4.5", key: "chirp-auk" },
  { label: "v4.5+", key: "chirp-bluejay" },
  { label: "v5", key: "chirp-crow" },
  { label: "v5.5", key: "chirp-fenix" },
];

const STORAGE_KEY = "camxora_playground";

interface Persisted {
  type: "music" | "sounds";
  mode: "simple" | "custom";
  version: string;
}

function loadPersisted(): Persisted {
  if (typeof window === "undefined") return { type: "music", mode: "simple", version: VERSIONS[0].key };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const p = JSON.parse(raw) as Partial<Persisted>;
      return {
        type: p.type === "sounds" ? "sounds" : "music",
        mode: p.mode === "custom" ? "custom" : "simple",
        version: VERSIONS.some((v) => v.key === p.version) ? (p.version as string) : VERSIONS[0].key,
      };
    }
  } catch {
    // ignore
  }
  return { type: "music", mode: "simple", version: VERSIONS[0].key };
}

interface TaskResult {
  job_id: string;
  type: string;
  status: string;
  result?: any;
  error?: string;
}

function clipAudio(clip: any): string | null {
  const media = clip?.media_urls?.[0]?.url;
  if (media) return media;
  return clip?.audio_url ?? clip?.video_url ?? null;
}

export default function PlaygroundPage() {
  const initial = loadPersisted();
  const [genType, setGenType] = useState<"music" | "sounds">(initial.type);
  const [mode, setMode] = useState<"simple" | "custom">(initial.mode);
  const [version, setVersion] = useState(initial.version);

  const [prompt, setPrompt] = useState("");
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [negativeTags, setNegativeTags] = useState("");
  const [instrumental, setInstrumental] = useState(false);
  const [loop, setLoop] = useState(false);
  const [tempo, setTempo] = useState("");
  const [soundKey, setSoundKey] = useState("");

  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [task, setTask] = useState<TaskResult | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Persist selections
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ type: genType, mode, version } satisfies Persisted));
    } catch {
      // ignore
    }
  }, [genType, mode, version]);

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
        if (data.status === "complete" || data.status === "error") {
          setBusy(false);
          return;
        }
        pollRef.current = setTimeout(tick, 3000);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Polling failed");
        setBusy(false);
      }
    };
    pollRef.current = setTimeout(tick, 1500);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setTask(null);
    try {
      let body: Record<string, unknown>;
      if (genType === "sounds") {
        body = {
          type: "sounds",
          prompt,
          model: version,
          loop,
          tempo: tempo ? Number(tempo) : null,
          key: soundKey || null,
        };
      } else {
        body = {
          type: "music",
          gpt_description_prompt: prompt,
          model: version,
        };
        if (mode === "custom") {
          body.title = title || undefined;
          body.tags = tags || undefined;
          body.negative_tags = negativeTags || undefined;
          body.instrumental = instrumental;
        }
      }
      const created = await apiFetch<{ job_id: string }>("/me/generate", {
        method: "POST",
        body: JSON.stringify(body),
      });
      poll(created.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
      setBusy(false);
    }
  }

  function segmented<T extends string>(value: T, set: (v: T) => void, options: { label: string; value: T }[]) {
    return (
      <div className="flex rounded-lg bg-white/5 p-1">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => set(o.value)}
            className={`flex-1 rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              value === o.value ? "grad-bg text-white" : "text-[var(--muted)] hover:text-white"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    );
  }

  const versionLabel = VERSIONS.find((v) => v.key === version)?.label ?? version;

  return (
    <div>
      <h1 className="text-2xl font-bold">Playground</h1>
      <p className="mt-1 text-sm text-[var(--muted)]">Generate music or sounds with a model version of your choice.</p>

      {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}

      <form onSubmit={onSubmit} className="glass mt-6 space-y-5 rounded-2xl p-6">
        {/* Generation type */}
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <div className="mb-2 text-xs text-[var(--muted)]">Generation type</div>
            {segmented<"music" | "sounds">(genType, setGenType, [
              { label: "Music", value: "music" },
              { label: "Sounds", value: "sounds" },
            ])}
          </div>
          {genType === "music" && (
            <div>
              <div className="mb-2 text-xs text-[var(--muted)]">Mode</div>
              {segmented<"simple" | "custom">(mode, setMode, [
                { label: "Simple", value: "simple" },
                { label: "Custom", value: "custom" },
              ])}
            </div>
          )}
        </div>

        {/* Version selector */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-[var(--muted)]">Model version</span>
            <span className="grad-text text-xs font-semibold">{versionLabel}</span>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {VERSIONS.map((v) => (
              <button
                key={v.key}
                type="button"
                onClick={() => setVersion(v.key)}
                className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  version === v.key
                    ? "border-transparent bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white"
                    : "border-[var(--border)] bg-white/5 text-[var(--muted)] hover:text-white"
                }`}
              >
                {v.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sounds settings */}
        {genType === "sounds" && (
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <div className="mb-2 text-xs text-[var(--muted)]">Type</div>
              <div className="flex rounded-lg bg-white/5 p-1">
                <button type="button" onClick={() => setLoop(false)} className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${!loop ? "grad-bg text-white" : "text-[var(--muted)] hover:text-white"}`}>
                  One-Shot
                </button>
                <button type="button" onClick={() => setLoop(true)} className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${loop ? "grad-bg text-white" : "text-[var(--muted)] hover:text-white"}`}>
                  Loop
                </button>
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">BPM</label>
              <input value={tempo} onChange={(e) => setTempo(e.target.value)} placeholder="Auto" className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">Key</label>
              <input value={soundKey} onChange={(e) => setSoundKey(e.target.value)} placeholder="Any" className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]" />
            </div>
          </div>
        )}

        {/* Description */}
        <div className="space-y-1">
          <label className="text-xs text-[var(--muted)]">
            {genType === "sounds" ? "Sound description" : "Song description"}
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
            required
            placeholder={
              genType === "sounds"
                ? "A soft ambient pad that slowly swells…"
                : "An upbeat synthwave track about neon city nights"
            }
            className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]"
          />
        </div>

        {/* Custom mode fields */}
        {genType === "music" && mode === "custom" && (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">Title</label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]" placeholder="Neon City Nights" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">Tags (comma-separated)</label>
              <input value={tags} onChange={(e) => setTags(e.target.value)} className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]" placeholder="synthwave, upbeat, 80s" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">Negative tags</label>
              <input value={negativeTags} onChange={(e) => setNegativeTags(e.target.value)} className="w-full rounded-lg border border-[var(--border)] bg-black/30 px-3 py-2 text-sm outline-none focus:border-[var(--violet)]" placeholder="distorted, harsh" />
            </div>
            <label className="flex items-center gap-2 self-end text-sm text-[var(--muted)]">
              <input type="checkbox" checked={instrumental} onChange={(e) => setInstrumental(e.target.checked)} className="accent-[var(--violet)]" /> Instrumental
            </label>
          </div>
        )}

        <button type="submit" disabled={busy} className="grad-bg w-full rounded-lg py-3 text-sm font-semibold text-white disabled:opacity-60">
          {busy ? "Generating…" : "Generate"}
        </button>
      </form>

      {task && (
        <div className="glass mt-6 rounded-2xl p-6">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-sm font-semibold">Task {task.job_id.slice(0, 8)}</span>
            <span className={`rounded-full px-2 py-0.5 text-xs ${task.status === "complete" ? "bg-[var(--emerald)]/15 text-[var(--emerald)]" : task.status === "error" ? "bg-red-500/15 text-red-300" : "bg-white/10 text-[var(--muted)]"}`}>
              {task.status}
            </span>
          </div>

          {task.status === "error" && <div className="text-sm text-red-300">{task.error}</div>}

          {task.status === "complete" && task.type === "music" && Array.isArray(task.result?.clips) && (
            <div className="space-y-4">
              {task.result.clips.map((c: any, i: number) => {
                const audio = clipAudio(c);
                return (
                  <div key={c.id ?? i} className="rounded-xl border border-[var(--border)] p-4">
                    <div className="mb-2 text-sm font-medium">{c.title ?? `Clip ${i + 1}`}</div>
                    {audio ? <audio controls src={audio} className="w-full" /> : <div className="text-sm text-[var(--muted)]">Audio URL not available yet.</div>}
                  </div>
                );
              })}
            </div>
          )}

          <details className="mt-4">
            <summary className="cursor-pointer text-xs text-[var(--muted)]">Raw response</summary>
            <pre className="mt-2 overflow-x-auto rounded-lg bg-black/30 p-3 text-xs">{JSON.stringify(task, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );
}
