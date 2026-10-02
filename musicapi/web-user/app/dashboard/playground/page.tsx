"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { downloadClip } from "@/components/playground";

type ModelOption = { label: string; key: string };

/**
 * Shown only while `GET /models` is unreachable, and identical to the current
 * live catalog — the v6 family. Suno has retired the older keys (V4 / V4.5 /
 * V4.5+ / V4.5-All / V5 / V5.5) and now silently remaps them to the current
 * default, so we no longer offer them in the UI.
 */
const FALLBACK_VERSIONS: ModelOption[] = [
  { label: "V6", key: "chirp-hawk" },
  { label: "V6-MINI", key: "chirp-goose" },
  { label: "V6-WILD", key: "chirp-hawk-wild" },
];

/**
 * Live Suno models first — the endpoint sorts the account default to the head,
 * so the default stays default — then the static fallback for any key the live
 * catalog did not report. A key present in both keeps the live entry.
 */
function mergeVersions(live: ModelOption[], fallback: ModelOption[]): ModelOption[] {
  const seen = new Set(live.map((m) => m.key));
  return [...live, ...fallback.filter((l) => !seen.has(l.key))];
}

/** Shape of `GET /models` — the live Suno catalog across the account pool. */
interface LiveModel {
  key: string;
  name: string;
  is_default: boolean;
}

const SOUND_KEYS = [
  "Any",
  "C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb",
  "G", "G#", "Ab", "A", "A#", "Bb", "B",
  "Cm", "C#m", "Dbm", "Dm", "D#m", "Ebm", "Em", "Fm", "F#m", "Gbm",
  "Gm", "G#m", "Abm", "Am", "A#m", "Bbm", "Bm",
];

const STORAGE_KEY = "camxora_playground";

interface Persisted {
  type: "music" | "sounds";
  mode: "simple" | "custom";
  musicVersion: string;
  soundVersion: string;
}

function loadPersisted(): Persisted {
  if (typeof window === "undefined")
    return { type: "music", mode: "simple", musicVersion: FALLBACK_VERSIONS[0].key, soundVersion: FALLBACK_VERSIONS[0].key };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const p = JSON.parse(raw) as Partial<Persisted>;
      return {
        type: p.type === "sounds" ? "sounds" : "music",
        mode: p.mode === "custom" ? "custom" : "simple",
        musicVersion: typeof p.musicVersion === "string" ? p.musicVersion : FALLBACK_VERSIONS[0].key,
        soundVersion: typeof p.soundVersion === "string" ? p.soundVersion : FALLBACK_VERSIONS[0].key,
      };
    }
  } catch {
    // ignore
  }
  return { type: "music", mode: "simple", musicVersion: FALLBACK_VERSIONS[0].key, soundVersion: FALLBACK_VERSIONS[0].key };
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

// Downloads go through the shared authenticated blob helper (httpOnly session
// cookie + 401 -> /login), never a raw <a href> that the browser fetches without
// the session and renders as a JSON error page in a new tab.
function ClipDownloadButtons({ clipId }: { clipId: string }) {
  const [busy, setBusy] = useState<"mp3" | "wav" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = async (format: "mp3" | "wav") => {
    try {
      setErr(null);
      setBusy(format);
      await downloadClip(clipId, format);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setErr(e instanceof Error ? e.message : `${format.toUpperCase()} download failed`);
    } finally {
      setBusy(null);
    }
  };
  const btn =
    "inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/80 hover:bg-white/10 transition disabled:cursor-not-allowed disabled:opacity-50";
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <button type="button" disabled={busy !== null} onClick={() => { void run("mp3"); }} className={btn}>
        {busy === "mp3" ? "Downloading…" : "⬇ Download MP3"}
      </button>
      <button type="button" disabled={busy !== null} onClick={() => { void run("wav"); }} className={btn}>
        {busy === "wav" ? "Downloading…" : "⬇ Download WAV"}
      </button>
      {err && <span className="text-xs text-red-300">{err}</span>}
    </div>
  );
}

function Switch({
  checked,
  onChange,
  label,
  labelFirst = false,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
  labelFirst?: boolean;
}) {
  const inner = (
    <>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
          checked ? "bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500" : "bg-white/10"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-[18px]" : "translate-x-0.5"
          }`}
        />
      </button>
      {label && <span className="text-sm text-white/70">{label}</span>}
    </>
  );
  return (
    <div className={`flex items-center gap-2 ${labelFirst ? "flex-row-reverse justify-between" : ""}`}>
      {inner}
    </div>
  );
}

function ModelDropdown({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: ModelOption[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);
  const cur = options.find((o) => o.key === value)?.label ?? options[0]?.label ?? "—";
  return (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-lg bg-white/5 px-3 py-1.5 text-sm text-white hover:bg-white/10"
      >
        {cur}
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5 opacity-60"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-1 w-36 overflow-hidden rounded-lg border border-white/10 bg-[#1a1a1d] py-1 shadow-2xl">
          {options.map((o) => (
            <button
              key={o.key}
              type="button"
              onClick={() => {
                onChange(o.key);
                setOpen(false);
              }}
              className={`block w-full px-3 py-1.5 text-left text-sm transition-colors ${
                value === o.key ? "bg-gradient-to-r from-violet-500/20 via-purple-500/20 to-fuchsia-500/20 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SoundKeyDropdown({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);
  const cur = value || "Sound Key";
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-lg bg-white/5 px-3 py-2 text-left text-sm text-white hover:bg-white/10"
      >
        <span className={value ? "text-white" : "text-white/50"}>{cur}</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5 opacity-60"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      {open && (
        <div className="absolute left-0 right-0 z-50 mt-1 max-h-56 overflow-y-auto rounded-lg border border-white/10 bg-[#1a1a1d] py-1 shadow-2xl">
          {SOUND_KEYS.map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => {
                onChange(k === "Any" ? "" : k);
                setOpen(false);
              }}
              className={`block w-full px-3 py-1.5 text-left text-sm transition-colors ${
                (k === "Any" && !value) || value === k ? "bg-gradient-to-r from-violet-500/20 via-purple-500/20 to-fuchsia-500/20 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
              }`}
            >
              {k}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PlaygroundPage() {
  const initial = loadPersisted();
  const [genType, setGenType] = useState<"music" | "sounds">(initial.type);
  const [mode, setMode] = useState<"simple" | "custom">(initial.mode);
  const [musicVersion, setMusicVersion] = useState(initial.musicVersion);
  const [soundVersion, setSoundVersion] = useState(initial.soundVersion);
  // Live Suno catalog, empty until /models answers. The dropdowns merge it with
  // the static v6 fallback, so the control renders immediately and degrades to
  // the current models if /models fails.
  const [liveModels, setLiveModels] = useState<ModelOption[]>([]);
  const versions = useMemo(() => mergeVersions(liveModels, FALLBACK_VERSIONS), [liveModels]);
  const soundVersions = useMemo(() => mergeVersions(liveModels, FALLBACK_VERSIONS), [liveModels]);
  const version = genType === "music" ? musicVersion : soundVersion;

  const [prompt, setPrompt] = useState("");
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [negativeTags, setNegativeTags] = useState("");
  const [instrumental, setInstrumental] = useState(false);
  const [refImages, setRefImages] = useState<string[]>([]);
  const [audioUrl, setAudioUrl] = useState("");
  const [videoUrl, setVideoUrl] = useState("");

  const [grabLyrics, setGrabLyrics] = useState(false);
  const [soundLoop, setSoundLoop] = useState(false);
  const [soundTempo, setSoundTempo] = useState("");
  const [soundKey, setSoundKey] = useState("");

  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [task, setTask] = useState<TaskResult | null>(null);
  const [lastBody, setLastBody] = useState<Record<string, unknown> | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ type: genType, mode, musicVersion, soundVersion } satisfies Persisted)
      );
    } catch {
      // ignore
    }
  }, [genType, mode, musicVersion, soundVersion]);

  // Pull the versions Suno actually offers our accounts. The endpoint already
  // sorts the account default first, so the head of the list is the default.
  useEffect(() => {
    let cancelled = false;
    apiFetch<{ models: LiveModel[] }>("/models")
      .then(({ models }) => {
        if (cancelled || !models?.length) return;
        setLiveModels(models.map((m) => ({ label: m.name.toUpperCase(), key: m.key })));
      })
      .catch(() => {
        // Keep the static fallback; a real generation problem surfaces on submit.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // A version persisted from a previous session may no longer be offered; move
  // it to the current default rather than submitting a model we cannot route.
  useEffect(() => {
    if (!versions.length) return;
    const keys = new Set(versions.map((v) => v.key));
    setMusicVersion((v) => (keys.has(v) ? v : versions[0].key));
  }, [versions]);

  useEffect(() => {
    if (!soundVersions.length) return;
    const keys = new Set(soundVersions.map((v) => v.key));
    setSoundVersion((v) => (keys.has(v) ? v : soundVersions[0].key));
  }, [soundVersions]);

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

  async function addRefImages(e: React.ChangeEvent<HTMLInputElement>) {
    const remaining = Math.max(0, 5 - refImages.length);
    const files = Array.from(e.target.files ?? []).slice(0, remaining);
    e.target.value = "";
    const readAsDataUrl = (f: File) =>
      new Promise<string>((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(String(r.result));
        r.onerror = () => reject(r.error);
        r.readAsDataURL(f);
      });
    try {
      const urls: string[] = [];
      for (const f of files) {
        if (f.size > 10 * 1024 * 1024) continue;
        const data = await readAsDataUrl(f);
        const res = await apiFetch<{ url: string }>("/me/upload/reference", {
          method: "POST",
          body: JSON.stringify({ data, kind: "image" }),
        });
        urls.push(res.url);
      }
      setRefImages((a) => [...a, ...urls].slice(0, 5));
    } catch {
      setError("Could not upload the selected image.");
    }
  }

  async function uploadRefAudio(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
      setError("Audio exceeds 50MB.");
      return;
    }
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(String(r.result));
        r.onerror = () => reject(r.error);
        r.readAsDataURL(file);
      });
      const res = await apiFetch<{ url: string }>("/me/upload/reference", {
        method: "POST",
        body: JSON.stringify({ data: dataUrl, kind: "audio" }),
      });
      setAudioUrl(res.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Audio upload failed");
    }
  }

  async function uploadRefVideo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 100 * 1024 * 1024) {
      setError("Video exceeds 100MB.");
      return;
    }
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(String(r.result));
        r.onerror = () => reject(r.error);
        r.readAsDataURL(file);
      });
      const res = await apiFetch<{ url: string }>("/me/upload/reference", {
        method: "POST",
        body: JSON.stringify({ data: dataUrl, kind: "video" }),
      });
      setVideoUrl(res.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Video upload failed");
    }
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
          model: soundVersion,
          loop: soundLoop,
          tempo: soundTempo ? Number(soundTempo) : null,
          key: soundKey || null,
          grab_lyrics: grabLyrics,
        };
      } else {
        body = {
          type: "music",
          gpt_description_prompt: prompt,
          model: musicVersion,
        };
        if (mode === "custom") {
          body.title = title || undefined;
          body.tags = tags || undefined;
          body.negative_tags = negativeTags || undefined;
          body.instrumental = instrumental;
        }
        if (refImages.length) body.imageUrls = refImages;
        if (audioUrl.trim()) body.audioUrls = [audioUrl.trim()];
        if (videoUrl.trim()) body.videoUrls = [videoUrl.trim()];
      }
      setLastBody(body);
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

  async function retryLast() {
    if (!lastBody || busy) return;
    setBusy(true);
    setError("");
    setTask(null);
    try {
      const created = await apiFetch<{ job_id: string }>("/me/generate", {
        method: "POST",
        body: JSON.stringify(lastBody),
      });
      poll(created.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setBusy(false);
    }
  }

  const promptLimit = genType === "music" ? 3000 : 500;
  const featureList = [
    "Utilizes a streaming response system, delivering results in as fast as 20 seconds.",
    "Stable and watermark-free.",
    "24/7 transcription monitoring for dual-layer protection.",
  ];

  return (
    <div className="pb-20">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">
          {genType === "sounds" ? "Sounds Generation" : "Music Generation"}
        </h1>
        <p className="mt-1 text-sm text-white/50">
          Generate music and sound effects with live inputs and responses.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {/* Left: form */}
        <form onSubmit={onSubmit} className="max-w-md space-y-4">
          {/* Type tabs pill */}
          <div className="flex rounded-xl bg-white/[0.03] p-1">
            {(["music", "sounds"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setGenType(t)}
                className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                  genType === t
                    ? "bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-md shadow-purple-900/30"
                    : "text-white/50 hover:text-white"
                }`}
              >
                {t === "music" ? "Music Generation" : "Sounds Generation"}
              </button>
            ))}
          </div>

          {genType === "music" ? (
            <>
              {/* Custom Mode pill row */}
              <div className="flex items-center justify-between rounded-xl bg-white/[0.03] px-3 py-2">
                <Switch checked={mode === "custom"} onChange={(v) => setMode(v ? "custom" : "simple")} label="Custom Mode" labelFirst />
                <ModelDropdown
                  value={musicVersion}
                  onChange={setMusicVersion}
                  options={versions}
                />
              </div>

              {/* Prompt */}
              <div>
                <div className="mb-1.5 text-xs font-medium text-white/50">Song Description</div>
                <div className="rounded-xl bg-white/[0.03] p-2">
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value.slice(0, promptLimit))}
                    rows={5}
                    placeholder="Describe the style of music and the topic you want, AI will generate lyrics for you."
                    className="w-full resize-none bg-transparent px-2 py-1 text-sm text-white placeholder-white/30 outline-none"
                  />
                  <div className="px-2 pb-1 text-right text-[11px] text-white/30">
                    {prompt.length} / {promptLimit}
                  </div>
                </div>
              </div>

              {/* Reference images — Suno's image upload (agentic_thinking) */}
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <div className="text-xs font-medium text-white/50">Reference Images (Optional)</div>
                  <div className="text-[11px] text-white/30">{refImages.length}/5</div>
                </div>
                <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-white/10 bg-white/[0.03] px-3 py-3 text-xs text-white/50 transition-colors hover:bg-white/[0.06]">
                  <span className="text-base leading-none">+</span> Add image
                  <input
                    type="file"
                    accept="image/jpeg,image/jpg,image/png,image/webp"
                    multiple
                    className="hidden"
                    onChange={(e) => void addRefImages(e)}
                  />
                </label>
                {refImages.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {refImages.map((src, i) => (
                      <div key={i} className="relative h-14 w-14 overflow-hidden rounded-lg border border-white/10">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={src} alt="reference" className="h-full w-full object-cover" />
                        <button
                          type="button"
                          onClick={() => setRefImages((a) => a.filter((_, j) => j !== i))}
                          className="absolute right-0 top-0 rounded-bl bg-black/70 px-1 text-[10px] text-white"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-1 text-[11px] text-white/30">JPEG / JPG / PNG / WEBP · Max 10MB</div>
              </div>

              {/* Reference audio — Suno upload → cover (melody retained) */}
              <div>
                <div className="mb-1.5 text-xs font-medium text-white/50">Reference Audio URL (Optional)</div>
                <input
                  value={audioUrl}
                  onChange={(e) => setAudioUrl(e.target.value)}
                  placeholder="https://…/song.mp3"
                  className="w-full rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2 text-sm outline-none focus:border-[var(--violet)] text-white"
                />
                <label className="mt-2 flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/50 transition-colors hover:bg-white/[0.06]">
                  ⬆ Upload audio file
                  <input type="file" accept="audio/*" className="hidden" onChange={(e) => void uploadRefAudio(e)} />
                </label>
                <div className="mt-1 text-[11px] text-white/30">
                  Suno re-arranges the track in your style, keeping its melody.
                </div>
              </div>

              {/* Reference video — first frame drives the image/agentic flow */}
              <div>
                <div className="mb-1.5 text-xs font-medium text-white/50">Reference Video (Optional)</div>
                <input
                  value={videoUrl}
                  onChange={(e) => setVideoUrl(e.target.value)}
                  placeholder="https://…/clip.mp4"
                  className="w-full rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2 text-sm outline-none focus:border-[var(--violet)] text-white"
                />
                <label className="mt-2 flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/50 transition-colors hover:bg-white/[0.06]">
                  ⬆ Upload video file
                  <input type="file" accept="video/mp4,video/quicktime,video/webm" className="hidden" onChange={(e) => void uploadRefVideo(e)} />
                </label>
                <div className="mt-1 text-[11px] text-white/30">A frame is used to inspire the song. MP4 / MOV / WEBM · Max 100MB</div>
              </div>

              {/* Custom mode fields */}
              {mode === "custom" && (
                <div className="grid gap-3 md:grid-cols-2">
                  <div>
                    <div className="mb-1 text-xs text-white/50">Title</div>
                    <input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="Song title"
                      className="w-full rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2 text-sm outline-none focus:border-[var(--violet)] text-white"
                    />
                  </div>
                  <div>
                    <div className="mb-1 text-xs text-white/50">Style of Music / Tags</div>
                    <input
                      value={tags}
                      onChange={(e) => setTags(e.target.value)}
                      placeholder="synthwave, upbeat, 80s"
                      className="w-full rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2 text-sm outline-none focus:border-[var(--violet)] text-white"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <div className="mb-1 text-xs text-white/50">Negative Tags</div>
                    <input
                      value={negativeTags}
                      onChange={(e) => setNegativeTags(e.target.value)}
                      placeholder="Tags to exclude"
                      className="w-full rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2 text-sm outline-none focus:border-[var(--violet)] text-white"
                    />
                  </div>
                </div>
              )}

              {/* Instrumental pill */}
              <div className="flex items-center justify-between rounded-xl bg-white/[0.03] px-3 py-2">
                <Switch checked={instrumental} onChange={setInstrumental} label="Instrumental" labelFirst />
              </div>
            </>
          ) : (
            <>
              {/* Sounds: just model on pill row */}
              <div className="flex items-center justify-end rounded-xl bg-white/[0.03] px-3 py-2">
                <ModelDropdown value={soundVersion} onChange={setSoundVersion} options={soundVersions} />
              </div>

              {/* Prompt */}
              <div>
                <div className="mb-1.5 text-xs font-medium text-white/50">Prompt</div>
                <div className="rounded-xl bg-white/[0.03] p-2">
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value.slice(0, promptLimit))}
                    rows={5}
                    placeholder="Enter prompt"
                    className="w-full resize-none bg-transparent px-2 py-1 text-sm text-white placeholder-white/30 outline-none"
                  />
                  <div className="px-2 pb-1 text-right text-[11px] text-white/30">
                    {prompt.length} / {promptLimit}
                  </div>
                </div>
              </div>

              {/* Grab Lyrics pill */}
              <div className="flex items-center justify-between rounded-xl bg-white/[0.03] px-3 py-2">
                <Switch checked={grabLyrics} onChange={setGrabLyrics} label="Grab Lyrics" labelFirst />
              </div>

              {/* Sound Key pill */}
              <div className="rounded-xl bg-white/[0.03] px-3 py-2">
                <SoundKeyDropdown value={soundKey} onChange={setSoundKey} />
              </div>

              {/* Sound Loop pill */}
              <div className="flex items-center justify-between rounded-xl bg-white/[0.03] px-3 py-2">
                <Switch checked={soundLoop} onChange={setSoundLoop} label="Sound Loop" labelFirst />
              </div>

              {/* Sound Tempo pill */}
              <div className="rounded-xl bg-white/[0.03] px-3 py-2">
                <div className="mb-1 text-xs text-white/50">Sound Tempo</div>
                <input
                  type="number"
                  value={soundTempo}
                  onChange={(e) => setSoundTempo(e.target.value)}
                  placeholder="Auto"
                  className="w-full rounded-lg border border-white/5 bg-transparent px-2 py-1.5 text-sm outline-none focus:border-[var(--violet)] text-white"
                />
              </div>
            </>
          )}

          {/* Generate */}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 py-3 text-sm font-semibold text-white shadow-lg shadow-purple-900/20 transition-opacity disabled:opacity-60"
          >
            {busy ? "Generating…" : genType === "sounds" ? "Generate Sound" : "Generate Music"}
          </button>
        </form>

        {/* Right: illustration + features */}
        <div className="flex flex-col items-center justify-center pt-4">
          <div className="relative mb-8 flex h-56 w-56 items-center justify-center">
            {/* Vinyl glow */}
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-violet-500/20 via-purple-500/20 to-fuchsia-500/20 blur-3xl" />
            {/* Music illustration: guitar, vinyl, mic, sheet */}
            <svg viewBox="0 0 200 200" className="relative h-full w-full" fill="none">
              <defs>
                <radialGradient id="vinyl" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#1a1a1f" />
                  <stop offset="60%" stopColor="#0c0c0e" />
                  <stop offset="100%" stopColor="#0a0a0c" />
                </radialGradient>
                <linearGradient id="guitarBody" x1="0" y1="1" x2="1" y2="0">
                  <stop offset="0%" stopColor="#B8860B" />
                  <stop offset="100%" stopColor="#DAA520" />
                </linearGradient>
              </defs>

              {/* Vinyl */}
              <circle cx="68" cy="92" r="56" fill="url(#vinyl)" stroke="#2a2a2f" strokeWidth="1" />
              <circle cx="68" cy="92" r="44" stroke="#1f1f24" strokeWidth="0.5" />
              <circle cx="68" cy="92" r="32" stroke="#1f1f24" strokeWidth="0.5" />
              <circle cx="68" cy="92" r="20" fill="#222227" />
              <circle cx="68" cy="92" r="4" fill="#8b5cf6" />

              {/* Guitar */}
              <g transform="translate(90, 40) rotate(25)">
                {/* Body */}
                <ellipse cx="40" cy="100" rx="28" ry="34" fill="url(#guitarBody)" />
                <circle cx="40" cy="100" r="10" fill="#1a1a1f" />
                {/* Neck */}
                <rect x="33" y="20" width="14" height="80" rx="3" fill="#c9a66b" />
                <line x1="40" y1="26" x2="40" y2="96" stroke="#806343" strokeWidth="1" />
                {/* Head */}
                <rect x="28" y="10" width="24" height="16" rx="3" fill="#a88038" />
                <circle cx="34" cy="18" r="1.5" fill="#333" />
                <circle cx="46" cy="18" r="1.5" fill="#333" />
              </g>

              {/* Microphone */}
              <g transform="translate(145, 120)">
                <rect x="-2" y="0" width="4" height="12" rx="2" fill="#c0c0c8" />
                <ellipse cx="0" cy="-6" rx="7" ry="10" fill="#e8e8ec" />
                <ellipse cx="0" cy="-6" rx="5" ry="7" fill="#2a2a31" />
                <line x1="-3" y1="-9" x2="3" y2="-9" stroke="#1a1a20" strokeWidth="0.6" />
                <line x1="-3" y1="-6" x2="3" y2="-6" stroke="#1a1a20" strokeWidth="0.6" />
                <line x1="-3" y1="-3" x2="3" y2="-3" stroke="#1a1a20" strokeWidth="0.6" />
                {/* Stand */}
                <rect x="-1" y="12" width="2" height="20" fill="#555" />
                <rect x="-10" y="32" width="20" height="3" rx="1" fill="#444" />
              </g>

              {/* Sheet music */}
              <g transform="translate(110, 130)">
                <rect x="0" y="0" width="40" height="48" rx="3" fill="#f5f3e7" />
                {/* Staff lines */}
                {[14, 20, 26, 32, 38].map((y, i) => (
                  <line key={i} x1="6" y1={y} x2="34" y2={y} stroke="#333" strokeWidth="0.5" />
                ))}
                {/* Notes */}
                <ellipse cx="14" cy="30" rx="3" ry="2" fill="#1a1a20" />
                <rect x="16.5" y="20" width="1" height="10" fill="#1a1a20" />
                <ellipse cx="22" cy="22" rx="3" ry="2" fill="#1a1a20" />
                <rect x="24.5" y="12" width="1" height="10" fill="#1a1a20" />
              </g>

              {/* Floating music note accent */}
              <g transform="translate(155, 60)" opacity="0.7">
                <ellipse cx="0" cy="0" rx="5" ry="4" fill="#8b5cf6" transform="rotate(-15)" />
                <rect x="4.5" y="-20" width="1.5" height="20" fill="#8b5cf6" />
                <path d="M6 -20 Q 16 -22 16 -12 Q 16 -10 13 -10 Q 10 -10 10 -8" stroke="#8b5cf6" strokeWidth="1.5" fill="none" />
              </g>
            </svg>
          </div>

          <ul className="w-full max-w-sm space-y-3 text-center text-sm text-white/60">
            {featureList.map((f) => (
              <li key={f} className="flex items-start gap-2">
                <span className="mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Results */}
      {task && (
        <div className="mt-10 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-white">Task {task.job_id.slice(0, 8)}</span>
            <span className={`rounded-full px-2 py-0.5 text-xs ${
              task.status === "complete"
                ? "bg-[var(--emerald)]/15 text-[var(--emerald)]"
                : task.status === "error"
                ? "bg-red-500/15 text-red-300"
                : "bg-white/10 text-white/50"
            }`}>
              {task.status}
            </span>
          </div>

          {task.status === "error" && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-3">
              <div className="text-sm text-red-300">{task.error}</div>
              <div className="mt-3 flex items-center justify-end gap-2">
                <button onClick={() => { setTask(null); setError(""); }} type="button" className="rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/70 hover:bg-white/10 disabled:opacity-50" disabled={busy}>Dismiss</button>
                {lastBody && (
                  <button
                    type="button"
                    onClick={retryLast}
                    disabled={busy}
                    className="rounded-md bg-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/15 disabled:opacity-50 disabled:cursor-not-allowed"
                  >↻ Retry</button>
                )}
              </div>
            </div>
          )}

          {task.status === "complete" && Array.isArray(task.result?.clips) && (
            <div className="grid gap-4 md:grid-cols-2">
              {task.result.clips.map((c: any, i: number) => {
                const audio = clipAudio(c);
                const id = c?.id;
                return (
                  <div key={c.id ?? i} className="rounded-xl border border-white/5 bg-[#161618] p-4">
                    <div className="mb-3 flex items-center gap-3">
                      <div className="grad-bg flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-lg">
                        ♪
                      </div>
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-white">{c.title ?? `Clip ${i + 1}`}</div>
                        <div className="truncate text-xs text-white/40">{c.tags ?? c.model ?? ""}</div>
                      </div>
                    </div>
                    {audio ? (
                      <audio controls src={audio} className="w-full [color-scheme:dark]" />
                    ) : (
                      <div className="text-sm text-white/50">Audio URL not available yet.</div>
                    )}
                    {id && <ClipDownloadButtons clipId={String(id)} />}
                  </div>
                );
              })}
            </div>
          )}

          <details>
            <summary className="cursor-pointer text-xs text-white/50">Raw response</summary>
            <pre className="mt-2 overflow-x-auto rounded-lg bg-black/30 p-3 text-xs text-white">{JSON.stringify(task, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );
}
