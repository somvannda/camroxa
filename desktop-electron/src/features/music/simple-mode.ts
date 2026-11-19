/** Types and small helpers for the Music page's Suno "Simple" mode. */

export interface SimpleClip {
  variant: string;
  label: string;
  audio_url: string;
  download_url: string;
  ready: boolean;
  package_status?: string;
  image_url?: string | null;
  duration_seconds?: number | null;
  title?: string;
  is_preview?: boolean;
  preview_seconds?: number | null;
}

export interface SimpleGeneration {
  id: string;
  title: string;
  lyrics: string;
  style: string;
  model: string;
  model_label: string;
  instrumental: boolean;
  status: string;
  error_message?: string | null;
  can_retry?: boolean;
  created_at?: string | null;
  is_preview?: boolean;
  unlockable?: boolean;
  clips: SimpleClip[];
}

export interface SimpleGenerationList {
  items: SimpleGeneration[];
  total: number;
  limit: number;
  offset: number;
}

export interface SimpleQuota {
  limit: number;
  used: number;
  remaining: number;
  credits_remaining: number;
  credits_per_song: number;
  premium_unlocked?: boolean;
  free_model?: string;
  can_download?: boolean;
}

export interface SimpleGenerateResponse {
  task_id: string;
  status: string;
  title: string;
  style: string;
  model?: string;
  model_label?: string;
  is_preview?: boolean;
  quota: SimpleQuota;
}

export const SIMPLE_MODELS = [
  { value: "V6", label: "V6 Pro" },
  { value: "V6_MINI", label: "V6 Mini" },
  { value: "V6_WILD", label: "V6 Wild" },
] as const;

export type SimpleModel = (typeof SIMPLE_MODELS)[number]["value"];

export function generationIsReady(generation: SimpleGeneration): boolean {
  const status = generation.status.toLowerCase();
  return status === "success" || status === "complete" || status === "completed" ||
    generation.clips.some((clip) => clip.ready);
}

export function generationIsFailed(generation: SimpleGeneration): boolean {
  const status = generation.status.toLowerCase();
  return status === "failed" || status === "error";
}

export function generationStatusLabel(generation: SimpleGeneration): string {
  if (generationIsReady(generation)) return "Ready";
  if (generationIsFailed(generation)) return "Failed";
  const status = generation.status.toLowerCase();
  if (status === "queued" || status === "pending") return "Queued";
  return "Generating";
}

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "";
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

export function clipFileName(generation: SimpleGeneration, variant: string, extension: string): string {
  const title = generation.title?.trim() || "song";
  const safe = title.replace(/[<>:"/\\|?*]+/g, "").replace(/\s+/g, " ").trim() || "song";
  const suffix = variant === "alt" ? "alt" : "primary";
  return `${safe.slice(0, 80)} (${suffix}).${extension}`;
}
