import type { JobEvent, JobPayload, WorkflowAction } from "../../shared/app-types";

type Unsubscribe = () => void;

type Listener = (event: JobEvent) => void;

let listeners: Listener[] = [];

function emit(event: JobEvent) {
  for (const l of listeners) l(event);
}

function nowIso() {
  return new Date().toISOString();
}

async function runMockWorkflow(action: WorkflowAction) {
  const jobId = crypto.randomUUID();
  const base = { jobId, jobType: "workflow" as const, action };
  emit({ ...base, status: "queued", message: "workflow queued", createdAt: nowIso() });
  emit({ ...base, status: "running", message: `${action} started`, progress: 0, createdAt: nowIso() });
  const steps = [
    { p: 10, m: `${action}: preparing` },
    { p: 35, m: `${action}: generating` },
    { p: 65, m: `${action}: processing` },
    { p: 90, m: `${action}: finalizing` },
  ];
  for (const s of steps) {
    await new Promise((r) => setTimeout(r, 420));
    emit({ ...base, status: "running", message: s.m, progress: s.p, createdAt: nowIso() });
  }
  emit({ ...base, status: "completed", message: "workflow completed", progress: 100, createdAt: nowIso() });
  return { jobId };
}

export const jobClient = {
  async enqueue(payload: JobPayload) {
    if (window.mgApi) return await window.mgApi.enqueueJob(payload);
    if (payload.jobType === "workflow") return await runMockWorkflow(payload.action);
    const jobId = crypto.randomUUID();
    if (payload.jobType === "suno") {
      emit({
        jobId,
        jobType: "suno",
        status: "failed",
        message: "suno automation is only available in Electron",
        createdAt: nowIso(),
      });
      return { jobId };
    }
    emit({
      jobId,
      jobType: "merge",
      status: "failed",
      message: "merge is only available in Electron",
      versionType: payload.versionType,
      createdAt: nowIso(),
    });
    return { jobId };
  },
  async cancel(jobId: string) {
    if (window.mgApi) return await window.mgApi.cancelJob(jobId);
    emit({ jobId, jobType: "workflow", status: "cancelled", message: "cancelled", createdAt: nowIso() });
    return { ok: true };
  },
  onEvent(listener: (event: JobEvent) => void): Unsubscribe {
    if (window.mgApi) return window.mgApi.onJobEvent(listener);
    listeners = [...listeners, listener];
    return () => {
      listeners = listeners.filter((x) => x !== listener);
    };
  },
};
