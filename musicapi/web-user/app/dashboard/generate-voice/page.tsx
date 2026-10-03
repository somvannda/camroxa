"use client";

import {
  Field,
  PageShell,
  PrimaryButton,
  inputCls,
  textareaCls,
  useJob,
} from "@/components/playground";
import { apiFetch } from "@/lib/api";
import { useCallback, useEffect, useRef, useState } from "react";

const SKILL_LEVELS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
  { value: "professional", label: "Professional" },
] as const;

type TaskBundle = {
  taskId?: string;
  audioUrl?: string;
};

const ENDPOINTS = {
  phrase: "voice_phrase",
  record: "voice_record",
  generate: "voice_generate",
} as const;

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
}

export default function GenerateVoicePage() {
  const [taskId, setTaskId] = useState("");
  const [voiceName, setVoiceName] = useState("My Voice");
  const [style, setStyle] = useState("Pop, Female Vocal");
  const [singerSkillLevel, setSingerSkillLevel] = useState("beginner");
  const [description, setDescription] = useState("created from uploaded voice");

  const [source, setSource] = useState<TaskBundle>({});
  const [validationPhrase, setValidationPhrase] = useState<TaskBundle & { phrase?: string }>({});
  const validationAudio: TaskBundle = {};
  const [selectOpen, setSelectOpen] = useState(false);

  const [costs, setCosts] = useState<Record<string, number>>({});
  useEffect(() => {
    apiFetch<{ pricing: Array<{ endpoint: string; model: string | null; credit_cost: number }> }>("/pricing")
      .then((p) => {
        const map: Record<string, number> = {};
        for (const row of p.pricing) {
          if (row.model === null && row.endpoint in ENDPOINTS) map[row.endpoint] = row.credit_cost;
        }
        setCosts(map);
      })
      .catch(() => {
        /* costs are advisory */
      });
  }, []);

  const generateCost = costs[ENDPOINTS.generate] ?? 0;
  const main = useJob();

  const canRun =
    !main.busy && (taskId || source.taskId) && voiceName.trim().length > 0;

  return (
    <PageShell
      title="Generate Voice"
      subtitle="Create a custom voice from a source audio sample."
      cardTitle="Generate Voice"
      cardSubtitle="Prepare the source and validation audio in the popup, then finish the voice generation here."
      error={main.error}
      output={
        <VoiceOverview
          main={main}
          source={source}
          validationPhrase={validationPhrase}
          validationAudio={validationAudio}
        />
      }
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!canRun) return;
          main.reset();
          const finalTaskId = taskId || source.taskId || "";
          main.submit("/me/voice-generate", {
            taskId: finalTaskId,
            voiceName,
            style,
            singerSkillLevel,
            description,
          });
        }}
        className="space-y-5"
      >
        <div>
          <button
            type="button"
            onClick={() => setSelectOpen(true)}
            className="rounded-md border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
          >
            Select Audio
          </button>
          <p className="mt-1.5 text-xs text-white/40">
            Upload or record a clean source sample. A validation phrase will be generated next.
          </p>
        </div>

        <Field label="taskId">
          <div className="relative">
            <input
              className={`${inputCls} pr-10`}
              placeholder="Not created yet"
              value={taskId || source.taskId || ""}
              onChange={(e) => setTaskId(e.target.value)}
            />
            <button
              type="button"
              onClick={() => { void navigator.clipboard.writeText(taskId || source.taskId || "").catch(() => {}); }}
              disabled={!taskId && !source.taskId}
              aria-label="Copy taskId"
              title="Copy taskId"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-white/40 transition hover:bg-white/5 hover:text-white disabled:opacity-30"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
                <rect x="9" y="9" width="13" height="13" rx="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
            </button>
          </div>
        </Field>

        <div className="grid gap-5 md:grid-cols-2">
          <Field label="voiceName">
            <input className={inputCls} placeholder="My Voice" value={voiceName} onChange={(e) => setVoiceName(e.target.value)} />
          </Field>
          <Field label="style">
            <input className={inputCls} placeholder="Pop, Female Vocal" value={style} onChange={(e) => setStyle(e.target.value)} />
          </Field>
        </div>

        <Field label="singerSkillLevel">
          <select className={inputCls} value={singerSkillLevel} onChange={(e) => setSingerSkillLevel(e.target.value)}>
            {SKILL_LEVELS.map((s) => (
              <option key={s.value} value={s.value} className="bg-[#0e0e10] text-white">
                {s.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="description">
          <textarea
            className={textareaCls}
            rows={2}
            placeholder="created from uploaded voice"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>

        <PrimaryButton type="submit" busy={main.busy} disabled={!canRun}>
          {generateCost > 0 ? `Generate Voice (${generateCost} credits)` : "Generate Voice"}
        </PrimaryButton>
      </form>

      {selectOpen && (
        <SelectAudioModal
          onClose={() => setSelectOpen(false)}
          onReady={(next) => {
            setSource(next.source);
            setValidationPhrase(next.phrase ? { phrase: next.phrase } : {});
            setSelectOpen(false);
          }}
        />
      )}
    </PageShell>
  );
}

function SelectAudioModal({
  onClose,
  onReady,
}: {
  onClose: () => void;
  onReady: (r: { source: TaskBundle; phrase?: string }) => void;
}) {
  const [sourceClipId, setSourceClipId] = useState("");
  const [sourcePreview, setSourcePreview] = useState("");
  const [phrase, setPhrase] = useState("");
  const [loadingPhrase, setLoadingPhrase] = useState(true);
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordSupported, setRecordSupported] = useState(true);
  const [error, setError] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Fetch the validation phrase (best-effort; the flow can continue without it).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const created = await apiFetch<{ job_id: string }>("/me/voice-phrase", {
          method: "POST",
          body: JSON.stringify({ prompt: "" }),
        });
        if (!created.job_id) throw new Error("No phrase task returned");
        for (let i = 0; i < 40; i++) {
          const t = await apiFetch<{ status: string; result?: { phrase?: string } }>(`/me/task/${created.job_id}`);
          if (t.status === "complete") {
            const p = t.result?.phrase;
            if (!cancelled && p) setPhrase(p);
            break;
          }
          if (t.status === "error") break;
          await new Promise((r) => setTimeout(r, 1500));
        }
      } catch {
        /* phrase is optional */
      } finally {
        if (!cancelled) setLoadingPhrase(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const uploadBlob = useCallback(async (blob: Blob) => {
    const previewUrl = URL.createObjectURL(blob);
    const dataUrl = await blobToDataUrl(blob);
    const res = await apiFetch<{ clip_id: string }>("/me/voice-source", {
      method: "POST",
      body: JSON.stringify({ data: dataUrl, uploadType: "voice_recording" }),
    });
    return { clipId: res.clip_id, previewUrl };
  }, []);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const { clipId, previewUrl } = await uploadBlob(file);
      setSourceClipId(clipId);
      setSourcePreview(previewUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function startRecording() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (ev) => ev.data.size > 0 && chunksRef.current.push(ev.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        setBusy(true);
        try {
          const { clipId, previewUrl } = await uploadBlob(new Blob(chunksRef.current, { type: "audio/webm" }));
          setSourceClipId(clipId);
          setSourcePreview(previewUrl);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Could not save the recording");
        } finally {
          setBusy(false);
        }
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
    } catch {
      setRecordSupported(false);
      setError("Microphone is not available in this browser. Please upload a file instead.");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => !busy && onClose()}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative w-full max-w-lg rounded-2xl border border-white/10 bg-[#14141c] p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-xl font-semibold text-white">Select Source Audio</h3>
        <p className="mt-1 text-sm text-white/60">Upload a clean sample, or record one now.</p>

        {/* Validation phrase */}
        <div className="mt-5 rounded-lg bg-white/[0.04] p-4">
          <div className="text-xs font-medium text-white/60">Validation phrase</div>
          <p className="mt-1 text-sm text-white/85">
            {loadingPhrase ? "Generating phrase…" : phrase || "Read anything clearly if no phrase is shown."}
          </p>
        </div>

        {/* Source */}
        <div className="mt-4 rounded-lg bg-white/[0.04] p-4">
          <div className="text-xs font-medium text-white/60">Source sample</div>
          {sourceClipId ? (
            <div className="mt-2 space-y-2">
              <audio src={sourcePreview} controls className="w-full" />
              <div className="break-all font-mono text-[11px] text-white/40">clip id: {sourceClipId}</div>
              <button
                type="button"
                onClick={() => {
                  setSourceClipId("");
                  setSourcePreview("");
                }}
                className="text-xs text-white/50 underline hover:text-white"
              >
                Remove and choose another
              </button>
            </div>
          ) : (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <label className={`inline-flex cursor-pointer items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white transition hover:bg-white/10 ${busy ? "cursor-wait opacity-60" : ""}`}>
                {busy ? "Uploading…" : "Upload audio"}
                <input type="file" accept="audio/*" className="hidden" disabled={busy} onChange={(e) => void handleFile(e)} />
              </label>
              {recordSupported && (
                <button
                  type="button"
                  onClick={recording ? stopRecording : startRecording}
                  disabled={busy}
                  className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm transition disabled:opacity-60 ${
                    recording
                      ? "border-red-500/40 bg-red-500/10 text-red-300"
                      : "border-white/10 bg-white/5 text-white hover:bg-white/10"
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full ${recording ? "animate-pulse bg-red-400" : "bg-white/40"}`} />
                  {recording ? "Stop recording" : "Record"}
                </button>
              )}
            </div>
          )}
        </div>

        {error && <div className="mt-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-300">{error}</div>}

        <div className="mt-5 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg px-4 py-2 text-sm text-white/70 transition hover:bg-white/5 hover:text-white disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onReady({ source: { taskId: sourceClipId, audioUrl: sourcePreview }, phrase })}
            disabled={!sourceClipId || busy}
            className="grad-bg rounded-lg px-5 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            Use this sample
          </button>
        </div>
      </div>
    </div>
  );
}

function VoiceOverview(props: {
  main: ReturnType<typeof useJob>;
  source: TaskBundle;
  validationPhrase: TaskBundle & { phrase?: string };
  validationAudio: TaskBundle;
}) {
  const { main, source, validationPhrase, validationAudio } = props;
  const [tab, setTab] = useState<"overview" | "json">("overview");
  const terminal = main.task && (main.task.status === "complete" || main.task.status === "error");
  const res = (main.task?.result as Record<string, unknown> | undefined) || {};
  const personaId = (res.personaId || res.persona_id || res.id) as string | undefined;

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
          <div className="space-y-5">
            <Kv title="Source Audio" value={source.audioUrl || source.taskId || null}>
              The source sample you selected.
            </Kv>
            <Kv title="Validation Phrase" value={validationPhrase.phrase || null}>
              Read this phrase when recording the validation sample.
            </Kv>
            <Kv title="Validation Audio" value={validationAudio.audioUrl || validationAudio.taskId || null}>
              The verification recording, if provided.
            </Kv>

            <div className="rounded-xl border border-white/5 bg-black/20 p-4">
              <div className="text-sm font-semibold text-white mb-2">Voice Result</div>
              <div className="grid gap-2 text-sm">
                <div className="flex gap-2 items-baseline">
                  <span className="text-white/40 min-w-[72px]">taskId:</span>
                  <code className="text-white/80 break-all font-mono text-xs">
                    {main.task?.job_id || "Not created yet"}
                  </code>
                </div>
                <div className="flex gap-2 items-baseline">
                  <span className="text-white/40 min-w-[72px]">voiceId:</span>
                  <span className="text-white/80 break-all font-mono text-xs">
                    {main.busy ? "Pending…" : terminal ? personaId || "Not ready yet" : "Not ready yet"}
                  </span>
                </div>
                {main.busy && !terminal && (
                  <div>
                    <div className="mt-2 h-1.5 w-full max-w-md overflow-hidden rounded-full bg-white/5">
                      <div className="h-full w-1/3 animate-[shimmer_1.4s_infinite] rounded-full bg-gradient-to-r from-transparent via-white/20 to-transparent" />
                    </div>
                    <p className="mt-1 text-xs text-white/50">Running… {main.task?.status}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <pre className="max-h-[520px] overflow-auto rounded-lg bg-black/40 p-4 text-xs leading-relaxed text-white/80">
{JSON.stringify(main.task || { status: "not run", source, validationPhrase, validationAudio }, null, 2)}
          </pre>
        )}
      </div>
    </section>
  );
}

function Kv(props: { title: string; value: string | null | undefined; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/5 bg-black/20 p-4">
      <div className="text-sm font-semibold text-white">{props.title}</div>
      <p className="mt-1 text-xs text-white/50">{props.children}</p>
      <div className="mt-3 text-sm text-white/85 break-all">
        {props.value ? (
          <code className="font-mono text-xs text-white/75">{props.value}</code>
        ) : (
          <span className="text-white/35">—</span>
        )}
      </div>
    </div>
  );
}
