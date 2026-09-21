import { config } from "./config.js";
import { apiHeaders, refreshJwt, resolveJwt } from "./auth.js";
import { captchaRequired, solveCaptcha } from "./captcha.js";

export interface BillingInfo {
  credits?: number;
  plan?: string;
  models?: unknown;
  [key: string]: unknown;
}

export interface LyricsResult {
  id?: string;
  status?: string;
  title?: string;
  text?: string;
  tags?: string;
  error_message?: string;
}

export interface GenerateMusicParams {
  /** description mode: Suno writes lyrics from this. */
  gptDescriptionPrompt?: string;
  /** custom mode: your own lyrics. */
  prompt?: string;
  tags?: string;
  title?: string;
  negativeTags?: string;
  instrumental?: boolean;
  model?: string;
}

export interface Clip {
  id: string;
  status: string;
  audio_url?: string;
  title?: string;
  media_urls?: Array<{ url?: string; content_type?: string }>;
  [key: string]: unknown;
}

async function sunoRequest(
  path: string,
  init: RequestInit = {},
  retryAuth = true,
): Promise<Response> {
  const jwt = await resolveJwt();
  const res = await fetch(`${config.apiUrl}${path}`, {
    ...init,
    headers: apiHeaders(jwt, config.deviceId, (init.headers as Record<string, string>) ?? {}),
  });

  // A single retry on auth failure, forcing a fresh JWT.
  if (retryAuth && (res.status === 401 || res.status === 403)) {
    await refreshJwt();
    return sunoRequest(path, init, false);
  }
  return res;
}

export async function getBillingInfo(): Promise<BillingInfo> {
  const res = await sunoRequest("/api/billing/info/");
  if (!res.ok) throw new Error(`billing/info failed (${res.status}): ${await res.text()}`);
  return (await res.json()) as BillingInfo;
}

export async function generateLyrics(prompt: string): Promise<string> {
  const res = await sunoRequest("/api/generate/lyrics/", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  if (!res.ok) throw new Error(`generate/lyrics failed (${res.status}): ${await res.text()}`);
  const data = (await res.json()) as { id?: string };
  if (!data.id) throw new Error("No lyrics id returned.");
  return data.id;
}

export async function getLyrics(id: string): Promise<LyricsResult> {
  const res = await sunoRequest(`/api/generate/lyrics/${id}`);
  if (!res.ok) throw new Error(`lyrics/${id} failed (${res.status}): ${await res.text()}`);
  return (await res.json()) as LyricsResult;
}

export async function generateMusic(params: GenerateMusicParams): Promise<Clip[]> {
  // Resolve the hCaptcha token: manual override > on-demand solve (only if required).
  let token = config.captchaToken;
  if (!token) {
    const required = await captchaRequired();
    token = required ? await solveCaptcha() : "";
  }

  const payload = {
    make_instrumental: params.instrumental ?? false,
    mv: params.model ?? config.model,
    prompt: params.prompt ?? "",
    generation_type: "TEXT",
    continue_at: null,
    continue_clip_id: null,
    task: null,
    token,
    gpt_description_prompt: params.gptDescriptionPrompt ?? "",
    tags: params.tags ?? "",
    title: params.title ?? "",
    negative_tags: params.negativeTags ?? "",
  };

  const res = await sunoRequest("/api/generate/v2/", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`generate/v2 failed (${res.status}): ${await res.text()}`);
  const data = (await res.json()) as { clips?: Clip[] };
  return data.clips ?? [];
}

/** Raw fetch of a clip (for debugging the polling endpoint). */
export async function getClipsRaw(ids: string[]): Promise<{ status: number; body: string }> {
  const res = await sunoRequest(`/api/feed/?ids=${ids.join(",")}`);
  const text = await res.text();
  return { status: res.status, body: text.slice(0, 2000) };
}

/** Poll clips by id until complete/error, or timeout. */
export async function pollClips(ids: string[],
  timeoutMs = 300_000,
  intervalMs = 5_000,
): Promise<Clip[]> {
  const deadline = Date.now() + timeoutMs;
  const query = ids.join(",");
  while (Date.now() < deadline) {
    const res = await sunoRequest(`/api/feed/?ids=${query}`);
    if (!res.ok) throw new Error(`feed failed (${res.status}): ${await res.text()}`);
    const data = (await res.json()) as Clip[];
    const clips = Array.isArray(data) ? data : [];
    if (clips.length > 0 && clips.every((c) => c.status === "complete" || c.status === "error")) {
      return clips;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Timed out waiting for clip completion.");
}
