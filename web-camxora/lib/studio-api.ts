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
