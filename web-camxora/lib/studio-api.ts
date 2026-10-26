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
