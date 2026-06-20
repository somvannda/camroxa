import path from "node:path";
import { promises as fs } from "node:fs";
import { createHash } from "node:crypto";

export type SunoApiModel = "V5" | "V5_5";

export type SunoApiGenerateInput = {
  apiKey: string;
  model: SunoApiModel;
  title: string;
  lyrics: string;
  style: string;
  instrumental: boolean;
  callbackUrl?: string;
};

export function hashSunoGenerateRequest(input: {
  model: string;
  title: string;
  prompt: string;
  style: string;
  instrumental: boolean;
}) {
  const normalized = {
    model: String(input.model || "").trim(),
    title: String(input.title || "").trim(),
    prompt: String(input.prompt || "").trim(),
    style: String(input.style || "").trim(),
    instrumental: Boolean(input.instrumental),
  };
  return createHash("sha256").update(JSON.stringify(normalized)).digest("hex");
}

export type SunoApiGenerateResult = { taskId: string };

export type SunoApiTaskStatus =
  | "PENDING"
  | "TEXT_SUCCESS"
  | "FIRST_SUCCESS"
  | "SUCCESS"
  | "CREATE_TASK_FAILED"
  | "GENERATE_AUDIO_FAILED"
  | "CALLBACK_EXCEPTION"
  | string;

export type SunoApiRecordInfo = {
  status: SunoApiTaskStatus;
  clips: Array<{ audioUrl?: string; audio_url?: string; id?: string; title?: string }>;
  raw: unknown;
};

function sanitizeFileName(input: string) {
  return String(input || "")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
}

async function httpJson<T>(url: string, init: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  const raw = await resp.text();
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try {
      const j = JSON.parse(raw) as unknown;
      if (j && typeof j === "object") {
        const rec = j as Record<string, unknown>;
        const topMsg = typeof rec.message === "string" ? rec.message : null;
        const err = rec.error && typeof rec.error === "object" ? (rec.error as Record<string, unknown>) : null;
        const errMsg = err && typeof err.message === "string" ? err.message : null;
        msg = topMsg || errMsg || msg;
      }
    } catch {
      if (raw.trim()) msg = raw.slice(0, 280);
    }
    throw new Error(msg);
  }
  return JSON.parse(raw) as T;
}

type GenerateResponse = {
  code?: number;
  msg?: string;
  data?: { taskId?: string; task_id?: string };
  taskId?: string;
  task_id?: string;
};

type RecordInfoResponse = {
  code?: number;
  msg?: string;
  data?: { status?: string; clips?: unknown; songs?: unknown };
  status?: string;
  clips?: unknown;
  songs?: unknown;
};

function assertApiOk(resp: { code?: number; msg?: string }) {
  if (typeof resp.code === "number" && resp.code !== 200) {
    const msg = String(resp.msg || "Suno API request failed").trim();
    throw new Error(`Suno API error ${resp.code}: ${msg}`);
  }
}

function asClips(value: unknown): SunoApiRecordInfo["clips"] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((x) => x && typeof x === "object")
    .map((x) => x as Record<string, unknown>)
    .map((r) => ({
      audioUrl: typeof r.audioUrl === "string" ? r.audioUrl : undefined,
      audio_url: typeof r.audio_url === "string" ? r.audio_url : undefined,
      id: typeof r.id === "string" ? r.id : undefined,
      title: typeof r.title === "string" ? r.title : undefined,
    }));
}

function pickFirstArray(root: unknown): unknown {
  if (!root || typeof root !== "object") return null;
  const r = root as Record<string, unknown>;
  if (Array.isArray(r.data)) return r.data;
  if (Array.isArray(r.sunoData)) return r.sunoData;
  if (r.response && typeof r.response === "object") {
    const rr = r.response as Record<string, unknown>;
    if (Array.isArray(rr.data)) return rr.data;
    if (Array.isArray(rr.sunoData)) return rr.sunoData;
  }
  return null;
}

export async function sunoApiGenerate(input: SunoApiGenerateInput): Promise<SunoApiGenerateResult> {
  const body = {
    customMode: true,
    instrumental: Boolean(input.instrumental),
    model: input.model,
    title: input.title,
    prompt: input.lyrics,
    style: input.style,
    callBackUrl: String(input.callbackUrl || "https://api.example.com/callback").trim(),
  };

  const res = await httpJson<GenerateResponse>("https://api.sunoapi.org/api/v1/generate", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${input.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  assertApiOk(res);

  const taskId = String(res.data?.taskId || res.data?.task_id || res.taskId || res.task_id || "").trim();
  if (!taskId) {
    const safe = JSON.stringify({ code: res.code, msg: res.msg, data: res.data ?? null }).slice(0, 500);
    throw new Error(`Suno API did not return taskId. Response: ${safe}`);
  }
  return { taskId };
}

export async function sunoApiGetRecordInfo(apiKey: string, taskId: string): Promise<SunoApiRecordInfo> {
  const url = new URL("https://api.sunoapi.org/api/v1/generate/record-info");
  url.searchParams.set("taskId", taskId);
  const res = await httpJson<RecordInfoResponse>(url.toString(), {
    method: "GET",
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
  });

  assertApiOk(res);

  const status = String(res.data?.status || res.status || "PENDING") as SunoApiTaskStatus;
  const nested = pickFirstArray(res.data);
  const d = res.data as unknown as Record<string, unknown> | undefined;
  const respObj = (d && typeof d.response === "object" ? (d.response as Record<string, unknown>) : null) as Record<string, unknown> | null;
  const clips = asClips(
    (d ? (d.clips as unknown) : undefined) ??
      (d ? (d.songs as unknown) : undefined) ??
      (d ? (d.sunoData as unknown) : undefined) ??
      (respObj ? (respObj.clips as unknown) : undefined) ??
      (respObj ? (respObj.songs as unknown) : undefined) ??
      (respObj ? (respObj.sunoData as unknown) : undefined) ??
      nested ??
      res.clips ??
      res.songs,
  );
  return { status, clips, raw: res };
}

export async function sunoApiWaitForTwoTracks(apiKey: string, taskId: string, timeoutMs: number) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const info = await sunoApiGetRecordInfo(apiKey, taskId);
    const urls = info.clips
      .map((c) => String(c.audioUrl || c.audio_url || "").trim())
      .filter(Boolean);

    if (urls.length >= 2) {
      return { status: info.status, audioUrls: urls.slice(0, 2), info };
    }
    if (info.status === "CREATE_TASK_FAILED" || info.status === "GENERATE_AUDIO_FAILED") {
      throw new Error(`Suno API failed: ${info.status}`);
    }

    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("Timed out waiting for Suno API generation");
}

export async function sunoApiTryGetTracks(apiKey: string, taskId: string) {
  const info = await sunoApiGetRecordInfo(apiKey, taskId);
  const urls = info.clips
    .map((c) => String(c.audioUrl || c.audio_url || "").trim())
    .filter(Boolean);
  return { status: info.status, audioUrls: urls.slice(0, 2), info };
}

export async function downloadToFile(url: string, outPath: string) {
  await fs.mkdir(path.dirname(outPath), { recursive: true });
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Download failed (${resp.status})`);
  const buf = Buffer.from(await resp.arrayBuffer());
  await fs.writeFile(outPath, buf);
  return outPath;
}

export function buildSunoOutputPaths(opts: { outputDir: string; title: string; trackNo?: number }) {
  const base = sanitizeFileName(opts.title);
  const prefix = Number.isFinite(opts.trackNo) ? `${Math.max(1, Math.floor(opts.trackNo ?? 1))}. ` : "";
  return {
    ok: path.join(opts.outputDir, `${prefix}${base}_OK.mp3`),
    alt: path.join(opts.outputDir, `${prefix}${base}_Alt.mp3`),
  };
}
