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

export default function RecoveryAudioPage() {
  const [sunoTaskId, setSunoTaskId] = useState("");
  const [callBackUrl, setCallBackUrl] = useState("");
  const { busy, task, error, submit, reset, retry, canRetry, retryCost } = useJob({ endpoint: "recovery_audio" });

  return (
    <PageShell
      title="Recovery Audio"
      subtitle="Recover playable audio links from an existing music generation task."
      cardTitle="Recovery Audio"
      cardSubtitle="Recover playable audio links from an existing music generation task."
      error={error}
      output={
        <OutputTabs
          task={task}
          busy={busy}
          readyTitle="Ready to recover"
          readyBody="Enter the original music generation task ID and click Run to recover its audio links."
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
          if (!sunoTaskId.trim()) return;
          reset();
          submit("/me/recovery", {
            sunoTaskId: sunoTaskId.trim(),
            callBackUrl: callBackUrl.trim() || undefined,
          });
        }}
        className="space-y-5"
      >
        <Field
          label="sunoTaskId"
          required
          help="The task ID of the original music generation task to recover"
        >
          <input
            className={inputCls}
            placeholder="Enter music generation task ID"
            value={sunoTaskId}
            onChange={(e) => setSunoTaskId(e.target.value)}
          />
        </Field>

        <Field
          label="callBackUrl"
          required
          help="Callback url notified when the recovery task finishes. The result is pushed to this address."
        >
          <input
            className={inputCls}
            placeholder="https://example.com/callback"
            value={callBackUrl}
            onChange={(e) => setCallBackUrl(e.target.value)}
          />
        </Field>

        <PrimaryButton type="submit" busy={busy} disabled={!sunoTaskId.trim()}>
          Recover Audio
        </PrimaryButton>
      </form>
    </PageShell>
  );
}
