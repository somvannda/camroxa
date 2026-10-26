import { musicAuthFetch } from "@/lib/auth-fetch";

export type StudioProjectData = {
  lanes?: unknown[];
  loopStart?: number;
  loopEnd?: number;
  zoom?: number;
  master?: number;
  [key: string]: unknown;
};

export type StudioProject = {
  id: string;
  title: string;
  major_version: number;
  bpm: number;
  time_signature: string;
  data?: StudioProjectData;
  created_at?: string | null;
  updated_at?: string | null;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as {
      error?: { message?: string };
      detail?: string;
    };
    if (payload.error?.message) return payload.error.message;
    if (typeof payload.detail === "string") return payload.detail;
  } catch {
    /* ignore */
  }
  return fallback;
}

async function studioJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await musicAuthFetch(path, init);
  if (!response.ok) {
    throw new Error(await readError(response, `Studio request failed (${response.status})`));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function listStudioProjects(
  limit = 20,
  offset = 0
): Promise<{ items: StudioProject[]; total: number }> {
  return studioJson(
    `/api/v3/web-music/studio/projects?limit=${limit}&offset=${offset}`
  );
}

export async function getStudioProject(id: string): Promise<StudioProject> {
  return studioJson(`/api/v3/web-music/studio/projects/${encodeURIComponent(id)}`);
}

export async function createStudioProject(input: {
  title: string;
  major_version?: number;
  bpm: number;
  time_signature?: string;
  data: StudioProjectData;
}): Promise<StudioProject> {
  return studioJson("/api/v3/web-music/studio/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      major_version: 2,
      time_signature: "4/4",
      ...input,
    }),
  });
}

export async function updateStudioProject(
  id: string,
  input: {
    title?: string;
    bpm?: number;
    time_signature?: string;
    data?: StudioProjectData;
  }
): Promise<StudioProject> {
  return studioJson(`/api/v3/web-music/studio/projects/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export type StudioOperation = {
  id: string;
  project_id?: string | null;
  task_id: string;
  variant: string;
  provider_clip_id: string;
  operation_type: string;
  mode: string;
  status: string;
  musicapi_job_id?: string | null;
  result?: {
    clips?: Array<{
      id?: string;
      title?: string;
      label?: string;
      audio_url?: string;
      durable_url?: string;
      durableUrl?: string;
      media_urls?: Array<{ url?: string; content_type?: string }>;
      image_url?: string | null;
      duration?: number;
      duration_seconds?: number | null;
      [key: string]: unknown;
    }>;
  } | null;
  credits_charged: number;
  error_message?: string | null;
};

export async function requestStudioStems(input: {
  taskId: string;
  variant: string;
  mode: "vocal" | "stems" | "advanced";
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/generations/${encodeURIComponent(input.taskId)}/stems`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      variant: input.variant,
      mode: input.mode,
      project_id: input.projectId || undefined,
    }),
  });
}

export async function getStudioOperation(id: string): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/operations/${encodeURIComponent(id)}`);
}

export async function requestStudioExtend(input: {
  taskId: string;
  variant: string;
  continueAt?: number | null;
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/generations/${encodeURIComponent(input.taskId)}/extend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      variant: input.variant,
      continue_at: input.continueAt ?? undefined,
      project_id: input.projectId || undefined,
    }),
  });
}

export async function requestStudioCover(input: {
  taskId: string;
  variant: string;
  prompt?: string;
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/generations/${encodeURIComponent(input.taskId)}/cover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      variant: input.variant,
      prompt: input.prompt || "",
      project_id: input.projectId || undefined,
    }),
  });
}

export async function requestStudioAddVocals(input: {
  taskId: string;
  variant: string;
  prompt: string;
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/generations/${encodeURIComponent(input.taskId)}/add-vocals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      variant: input.variant,
      prompt: input.prompt,
      project_id: input.projectId || undefined,
    }),
  });
}

export async function requestStudioAddInstrumental(input: {
  taskId: string;
  variant: string;
  prompt: string;
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/generations/${encodeURIComponent(input.taskId)}/add-instrumental`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      variant: input.variant,
      prompt: input.prompt,
      project_id: input.projectId || undefined,
    }),
  });
}

export async function requestStudioReplaceSection(input: {
  taskId: string;
  variant: string;
  startS: number;
  endS: number;
  lyrics: string;
  prompt?: string;
  model?: string | null;
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/generations/${encodeURIComponent(input.taskId)}/replace-section`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      variant: input.variant,
      start_s: input.startS,
      end_s: input.endS,
      lyrics: input.lyrics,
      prompt: input.prompt || "",
      model: input.model || undefined,
      project_id: input.projectId || undefined,
    }),
  });
}

export type StudioPricing = {
  edit: number;
  stems_2: number;
  stems_12: number;
};

export async function getStudioPricing(): Promise<StudioPricing> {
  return studioJson("/api/v3/web-music/studio/pricing");
}

export type StudioUpload = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  duration_seconds?: number | null;
  url: string;
};

export async function uploadStudioAudio(
  file: File,
  durationSeconds?: number | null
): Promise<StudioUpload> {
  const form = new FormData();
  form.append("file", file);
  if (durationSeconds != null) form.append("duration_seconds", String(durationSeconds));
  const response = await musicAuthFetch("/api/v3/web-music/studio/uploads", {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Upload failed (${response.status})`));
  }
  return (await response.json()) as StudioUpload;
}

export async function getStudioUploadUrl(id: string): Promise<string> {
  const upload = await studioJson<StudioUpload>(
    `/api/v3/web-music/studio/uploads/${encodeURIComponent(id)}`
  );
  return upload.url;
}
