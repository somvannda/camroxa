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

function CopyIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

export default function CheckVoicePage() {
  const [taskId, setTaskId] = useState("");
  const { busy, task, error, submit, reset, retry, canRetry, retryCost } = useJob({ endpoint: "voice_validate" });

  const canRun = !busy && !!taskId.trim();

  async function copyTaskId() {
    try {
      await navigator.clipboard.writeText(taskId.trim());
    } catch {
      /* ignore */
    }
  }

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
          submit("/me/voice-validate", { taskId: taskId.trim() });
        }}
        className="space-y-5"
      >
        <Field label="taskId" required>
          <div className="relative">
            <input
              className={`${inputCls} pr-11`}
              placeholder="xxx_task_id_xxx"
              value={taskId}
              onChange={(e) => setTaskId(e.target.value)}
            />
            <button
              type="button"
              onClick={copyTaskId}
              disabled={!taskId.trim()}
              aria-label="Copy taskId"
              title="Copy taskId"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-white/40 transition hover:bg-white/5 hover:text-white disabled:opacity-30"
            >
              <CopyIcon className="w-4 h-4" />
            </button>
          </div>
        </Field>

        <PrimaryButton type="submit" busy={busy} disabled={!canRun}>
          Check Availability
        </PrimaryButton>
      </form>
    </PageShell>
  );
}
