import { musicAuthFetch } from "@/lib/auth-fetch";
import type { WebMusicGeneration } from "@/lib/library-api";

export type GenerateSongInput = {
  mode: "simple" | "advanced";
  prompt?: string;
  lyrics?: string;
  style?: string;
  title?: string;
  instrumental?: boolean;
  model?: string;
  negative_tags?: string;
  vocal_gender?: "m" | "f" | "both";
  style_weight?: number;
  weirdness_constraint?: number;
  audio_weight?: number;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: string | { message?: string };
      error?: { message?: string };
    };
    if (typeof data.detail === "string") return data.detail;
    if (data.detail && typeof data.detail === "object" && data.detail.message) {
      return data.detail.message;
    }
    if (data.error?.message) return data.error.message;
  } catch {
    /* ignore */
  }
  return fallback;
}

export async function generateSong(input: GenerateSongInput): Promise<{
  task_id: string;
  status: string;
  title: string;
  style: string;
}> {
  const response = await musicAuthFetch("/api/v3/web-music/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Generation failed (${response.status})`));
  }
  return (await response.json()) as {
    task_id: string;
    status: string;
    title: string;
    style: string;
  };
}

export async function fetchGeneration(id: string): Promise<WebMusicGeneration> {
  const response = await musicAuthFetch(
    `/api/v3/web-music/generations/${encodeURIComponent(id)}`
  );
  if (!response.ok) {
    throw new Error(await readError(response, `Could not load generation (${response.status})`));
  }
  return (await response.json()) as WebMusicGeneration;
}

export async function generateLyrics(prompt: string): Promise<{ lyrics: string; title: string }> {
  const response = await musicAuthFetch("/api/v3/web-music/generate-draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  if (!response.ok) {
    throw new Error(await readError(response, `Could not generate lyrics (${response.status})`));
  }
  return (await response.json()) as { lyrics: string; title: string };
}
