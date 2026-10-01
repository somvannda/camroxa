"use client";

import {
  Field,
  OutputTabs,
  PageShell,
  PrimaryButton,
  inputCls,
  useJob,
} from "@/components/playground";
import { useState } from "react";

export default function CheckVoicePage() {
  const [taskId, setTaskId] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [mode, setMode] = useState<"task" | "audio">("task");
  const { busy, task, error, submit, reset, retry, canRetry, retryCost } = useJob({ endpoint: "voice_validate" });

  const canRun = !busy && (mode === "task" ? taskId.trim() : audioUrl.trim());

  return (
    <PageShell
      title="Check Voice"
      subtitle="Query whether a generated voice is available."
      cardTitle="Query Voice Availability"
      cardSubtitle="Enter the generated taskId and query the voice availability result."
      error={error}
      output={
        <OutputTabs
          task={task}
          busy={busy}
          readyTitle="Not Checked"
          readyBody="Run the query to see whether this voice is available."
          kind="result"
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
          submit("/me/voice-validate", {
            taskId: taskId.trim() || undefined,
            audioUrl: audioUrl.trim() || undefined,
          });
        }}
        className="space-y-5"
      >
        <div className="flex rounded-xl bg-black/20 p-1 text-sm">
          {([
            { k: "task", label: "By taskId" },
            { k: "audio", label: "By audio URL" },
          ] as const).map((o) => (
            <button
              key={o.k}
              type="button"
              onClick={() => setMode(o.k)}
              className={`flex-1 rounded-lg px-3 py-2 transition ${
                mode === o.k ? "bg-white/10 text-white" : "text-white/55 hover:text-white/85"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>

        {mode === "task" ? (
          <Field label="taskId">
            <input
              className={inputCls}
              placeholder="xxx_task_id_xxx"
              value={taskId}
              onChange={(e) => setTaskId(e.target.value)}
            />
          </Field>
        ) : (
          <Field label="audioUrl">
            <input
              className={inputCls}
              placeholder="https://example.com/validation.wav"
              value={audioUrl}
              onChange={(e) => setAudioUrl(e.target.value)}
            />
          </Field>
        )}

        <PrimaryButton type="submit" busy={busy} disabled={!canRun}>
          Check Availability
        </PrimaryButton>
      </form>
    </PageShell>
  );
}
