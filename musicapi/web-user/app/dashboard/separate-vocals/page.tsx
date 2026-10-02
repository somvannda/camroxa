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
import { useState } from "react";

type SeparationType = "vocal" | "stems" | "advanced";

export default function SeparateVocalsPage() {
  const [useCustomAudio, setUseCustomAudio] = useState(false);
  const [taskId, setTaskId] = useState("");
  const [audioId, setAudioId] = useState("");
  const [separationType, setSeparationType] = useState<SeparationType>("vocal");
  const [trackName, setTrackName] = useState("");

  const { busy, task, error, submit, reset, retry, canRetry } = useJob();

  const canRun = !busy && (useCustomAudio ? audioId : taskId || audioId);

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
            trackName,
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
          <Field label="trackName" required>
            <input
              className={inputCls}
              placeholder="Custom track name, e.g. drums"
              value={trackName}
              onChange={(e) => setTrackName(e.target.value)}
            />
          </Field>
        )}

        <PrimaryButton type="submit" busy={busy} disabled={!canRun}>
          Separate Vocals
        </PrimaryButton>
      </form>
    </PageShell>
  );
}
