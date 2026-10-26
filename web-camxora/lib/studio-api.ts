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
  permission?: "view" | "edit";
  read_only?: boolean;
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

export type StudioProjectVersion = {
  id: string;
  project_id: string;
  label?: string | null;
  title: string;
  bpm: number;
  time_signature: string;
  created_at?: string | null;
};

export async function listStudioProjectVersions(
  projectId: string,
  limit = 30
): Promise<{ items: StudioProjectVersion[]; total: number }> {
  return studioJson(
    `/api/v3/web-music/studio/projects/${encodeURIComponent(projectId)}/versions?limit=${limit}`
  );
}

export async function createStudioProjectVersion(
  projectId: string,
  label?: string
): Promise<StudioProjectVersion> {
  return studioJson(
    `/api/v3/web-music/studio/projects/${encodeURIComponent(projectId)}/versions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: label || undefined }),
    }
  );
}

export async function restoreStudioProjectVersion(
  projectId: string,
  versionId: string
): Promise<StudioProject> {
  return studioJson(
    `/api/v3/web-music/studio/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/restore`,
    { method: "POST" }
  );
}

export type StudioProjectShare = {
  id: string;
  token: string;
  path: string;
  expires_at: string;
  permission?: "view" | "edit";
};

export async function createStudioProjectShare(
  projectId: string,
  expiresDays = 7,
  permission: "view" | "edit" = "view"
): Promise<StudioProjectShare> {
  return studioJson(
    `/api/v3/web-music/studio/projects/${encodeURIComponent(projectId)}/shares`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expires_days: expiresDays, permission }),
    }
  );
}

export async function getStudioSharedProject(token: string): Promise<StudioProject> {
  return studioJson(`/api/v3/web-music/studio/shares/${encodeURIComponent(token)}`);
}

export type StudioShareComment = {
  id: string;
  author_name: string;
  body: string;
  created_at?: string | null;
};

export async function listStudioShareComments(
  token: string
): Promise<{ items: StudioShareComment[] }> {
  return studioJson(
    `/api/v3/web-music/studio/shares/${encodeURIComponent(token)}/comments`
  );
}

export async function addStudioShareComment(
  token: string,
  input: { authorName: string; body: string }
): Promise<StudioShareComment> {
  return studioJson(
    `/api/v3/web-music/studio/shares/${encodeURIComponent(token)}/comments`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        author_name: input.authorName || "Guest",
        body: input.body,
      }),
    }
  );
}

export async function listStudioProjectComments(
  projectId: string,
  limit = 100
): Promise<{ items: StudioShareComment[] }> {
  return studioJson(
    `/api/v3/web-music/studio/projects/${encodeURIComponent(projectId)}/comments?limit=${limit}`
  );
}

export async function forkStudioSharedProject(token: string): Promise<StudioProject> {
  return studioJson(
    `/api/v3/web-music/studio/shares/${encodeURIComponent(token)}/fork`,
    { method: "POST" }
  );
}

export async function updateStudioSharedProject(
  token: string,
  input: {
    title?: string;
    bpm?: number;
    time_signature?: string;
    data?: StudioProjectData;
    expectedUpdatedAt?: string | null;
  }
): Promise<StudioProject> {
  return studioJson(
    `/api/v3/web-music/studio/shares/${encodeURIComponent(token)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...input,
        expected_updated_at: input.expectedUpdatedAt || undefined,
      }),
    }
  );
}

export type StudioPresence = {
  user_id: string;
  display_name: string;
  last_seen?: string | null;
};

export async function touchStudioPresence(
  token: string,
  displayName: string
): Promise<{ items: StudioPresence[] }> {
  return studioJson(
    `/api/v3/web-music/studio/shares/${encodeURIComponent(token)}/presence`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName }),
    }
  );
}

export async function deleteStudioProject(id: string): Promise<void> {
  const response = await musicAuthFetch(
    `/api/v3/web-music/studio/projects/${encodeURIComponent(id)}`,
    { method: "DELETE" }
  );
  if (!response.ok) {
    throw new Error(await readError(response, `Delete project failed (${response.status})`));
  }
}

export async function revokeStudioProjectShare(
  projectId: string,
  shareId: string
): Promise<void> {
  const response = await musicAuthFetch(
    `/api/v3/web-music/studio/projects/${encodeURIComponent(projectId)}/shares/${encodeURIComponent(shareId)}`,
    { method: "DELETE" }
  );
  if (!response.ok) {
    throw new Error(await readError(response, `Revoke share failed (${response.status})`));
  }
}

export async function requestStudioRemaster(input: {
  taskId: string;
  variant: string;
  model?: string | null;
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/generations/${encodeURIComponent(input.taskId)}/remaster`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      variant: input.variant,
      model: input.model || undefined,
      project_id: input.projectId || undefined,
    }),
  });
}

export async function requestStudioMashup(input: {
  clips: Array<{ taskId: string; variant: string }>;
  prompt?: string;
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson("/api/v3/web-music/studio/mashup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task_ids: input.clips.map((clip) => clip.taskId),
      variants: input.clips.map((clip) => clip.variant),
      prompt: input.prompt || "",
      project_id: input.projectId || undefined,
    }),
  });
}

export type StudioLyricWord = {
  word?: string;
  text?: string;
  start_s?: number;
  end_s?: number;
  start?: number;
  end?: number;
};

export type StudioLyrics = {
  clip_id: string;
  lyrics: string;
  aligned_words: StudioLyricWord[];
};

export async function getStudioLyrics(input: {
  taskId: string;
  variant: string;
}): Promise<StudioLyrics> {
  return studioJson(
    `/api/v3/web-music/studio/generations/${encodeURIComponent(input.taskId)}/lyrics?variant=${encodeURIComponent(input.variant)}`
  );
}

export async function requestStudioUploadExtend(input: {
  uploadId: string;
  prompt?: string;
  continueAt?: number | null;
  title?: string;
  tags?: string;
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/uploads/${encodeURIComponent(input.uploadId)}/extend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: input.prompt || "",
      continue_at: input.continueAt ?? undefined,
      title: input.title || "",
      tags: input.tags || "",
      project_id: input.projectId || undefined,
    }),
  });
}

export async function requestStudioUploadCover(input: {
  uploadId: string;
  prompt?: string;
  coverStartS?: number | null;
  coverEndS?: number | null;
  title?: string;
  tags?: string;
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/uploads/${encodeURIComponent(input.uploadId)}/cover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: input.prompt || "",
      cover_start_s: input.coverStartS ?? undefined,
      cover_end_s: input.coverEndS ?? undefined,
      title: input.title || "",
      tags: input.tags || "",
      project_id: input.projectId || undefined,
    }),
  });
}

export async function requestStudioCoverImage(input: {
  taskId: string;
  variant: string;
  prompt: string;
  projectId?: string | null;
}): Promise<StudioOperation> {
  return studioJson(`/api/v3/web-music/studio/generations/${encodeURIComponent(input.taskId)}/cover-image`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      variant: input.variant,
      prompt: input.prompt,
      project_id: input.projectId || undefined,
    }),
  });
}
