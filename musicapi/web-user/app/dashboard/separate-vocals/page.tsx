"use client";

import {
  ChoiceCard,
  Field,
  OutputTabs,
  PageShell,
  PrimaryButton,
  Switch,
  inputCls,
  useJob,
} from "@/components/playground";
import { apiFetch } from "@/lib/api";
import { useState } from "react";

type SeparationType = "vocal" | "stems" | "advanced";

// Common stem names offered by sunoapi.org's Advanced Split.
const STEM_NAMES = [
  "Vocals", "Instrumental", "Backing Vocals", "Lead Vocal", "Drums", "Bass", "Guitar",
  "Acoustic Guitar", "Electric Guitar", "Piano", "Keyboard", "Percussion", "Strings",
  "Synthesizer", "Effects", "Brass", "Woodwinds", "Cello", "Violin", "Saxophone",
  "Trumpet", "Flute", "Organ", "Banjo", "Ukulele", "Harp", "Choir", "Kick", "Snare",
  "Hi-Hat", "Cymbals", "Toms", "Claps", "Riser", "Foley", "Ambience", "Sub Bass",
  "Synth Bass", "Arpeggio", "Pads", "Plucks", "Bell", "Marimba", "Xylophone",
];

export default function SeparateVocalsPage() {
  const [useCustomAudio, setUseCustomAudio] = useState(false);
  const [taskId, setTaskId] = useState("");
  const [audioId, setAudioId] = useState("");
  const [separationType, setSeparationType] = useState<SeparationType>("vocal");
  const [stemName, setStemName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadName, setUploadName] = useState("");
  const [uploadError, setUploadError] = useState("");

  async function handleAudioFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) {
      setUploadError("File size exceeds 20MB limit");
      return;
    }
    setUploading(true);
    setUploadError("");
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(String(r.result));
        r.onerror = () => reject(r.error);
        r.readAsDataURL(file);
      });
      const resp = await apiFetch<{ clip_id: string }>("/me/voice-source", {
        method: "POST",
        body: JSON.stringify({ data: dataUrl, uploadType: "file_upload" }),
      });
      setAudioId(resp.clip_id);
      setUploadName(file.name);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  const { busy, task, error, submit, reset, retry, canRetry, retryCost } = useJob({ endpoint: "stems" });

  const canRun =
    !busy &&
    (useCustomAudio ? !!audioId.trim() : !!taskId.trim() && !!audioId.trim()) &&
    (separationType !== "advanced" || !!stemName.trim());

  return (
    <PageShell
      title="Separate Vocals"
      subtitle="Separate vocals, accompaniment, and stems from generated music."
      cardTitle="Separate Vocals"
      cardSubtitle="Use generated music or custom audio to separate vocals, accompaniment, or stems."
      error={error}
      output={
        <OutputTabs
          task={task}
          busy={busy}
          readyTitle="Ready to separate"
          readyBody="Enter a generated taskId and audioId to split vocals and instruments."
          kind="clips"
          retry={retry}
          canRetry={canRetry}
          retryCost={retryCost}
          onReset={reset}
        />
      }
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!canRun) return;
          reset();
          submit("/me/stems", {
            useCustomAudio,
            taskId,
            audioId,
            separationType,
            stemName: separationType === "advanced" ? stemName : undefined,
            trackName: separationType === "advanced" ? stemName : undefined,
          });
        }}
        className="space-y-5"
      >
        <div className="flex items-center justify-between rounded-xl border border-white/5 bg-black/20 px-4 py-3">
          <div>
            <div className="text-sm font-medium text-white">Use uploaded custom audio</div>
            <p className="text-xs text-white/45">Upload an audio file or use an Audio ID without a taskId.</p>
          </div>
          <Switch checked={useCustomAudio} onChange={setUseCustomAudio} />
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          {!useCustomAudio && (
            <Field label="taskId" required help="Enter task ID from music generation">
              <input
                className={inputCls}
                placeholder="Enter task ID from music generation"
                value={taskId}
                onChange={(e) => setTaskId(e.target.value)}
              />
            </Field>
          )}

          <Field label="audioId" required help="Enter audio ID from callback data">
            <input
              className={inputCls}
              placeholder="Enter audio ID from callback data"
              value={audioId}
              onChange={(e) => setAudioId(e.target.value)}
            />
          </Field>
        </div>

        {useCustomAudio && (
          <div>
            <Field label="Upload audio" help="MP3, WAV, OGG, M4A, FLAC, AAC · Max 20MB">
              <label className={`flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-white/10 bg-white/[0.03] px-3 py-3 text-xs text-white/55 transition hover:bg-white/[0.06] ${uploading ? "cursor-wait opacity-60" : ""}`}>
                {uploading ? "Uploading…" : uploadName || "Click or drag audio file to upload"}
                <input type="file" accept="audio/*" className="hidden" disabled={uploading} onChange={(e) => void handleAudioFile(e)} />
              </label>
            </Field>
            {uploadError && <p className="mt-1 text-xs text-red-300">{uploadError}</p>}
            <p className="mt-1 text-xs text-white/40">Choose one audio source — upload a file or enter an Audio ID.</p>
          </div>
        )}

        <Field label="Separation Type">
          <ChoiceCard
            value={separationType}
            onChange={(v) => setSeparationType(v as SeparationType)}
            options={[
              {
                key: "vocal",
                title: "Vocal Separation",
                description: "Separate vocals and accompaniment into two tracks.",
              },
              {
                key: "stems",
                title: "Multi-Stem Separation",
                description: "Separate vocals and instruments into multiple tracks.",
              },
              {
                key: "advanced",
                title: "Advanced Split",
                description: "Advanced stem separation with custom track name.",
              },
            ]}
          />
        </Field>

        {separationType === "advanced" && (
          <Field label="Stem Name" required help="Select the stem to extract">
            <input
              className={inputCls}
              list="stem-name-options"
              placeholder="Select stem name"
              value={stemName}
              onChange={(e) => setStemName(e.target.value)}
            />
            <datalist id="stem-name-options">
              {STEM_NAMES.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </Field>
        )}

        <PrimaryButton type="submit" busy={busy} disabled={!canRun}>
          Separate Vocals
        </PrimaryButton>
      </form>
    </PageShell>
  );
}
