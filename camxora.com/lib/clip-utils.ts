import type { WebMusicClip, WebMusicGeneration } from "@/lib/library-api";

export type ClipDownloadKind = "mp3" | "wav" | "lrc" | "srt";

export function statusLabel(status: string): string {
  return (status || "draft").replace(/_/g, " ");
}

export function clipVersionLabel(variant?: string | null): string {
  return variant === "alt" ? "Version 2" : "Version 1";
}

export function generationClips(generation: WebMusicGeneration): WebMusicClip[] {
  if (generation.clips?.length) return generation.clips;
  return [
    {
      variant: "ok",
      label: generation.title,
      audio_url: "",
      download_url: "",
      ready: false,
    },
    {
      variant: "alt",
      label: generation.title,
      audio_url: "",
      download_url: "",
      ready: false,
    },
  ];
}

export function clipTrackKey(songId: string, variant: string): string {
  return `${songId}:${variant}`;
}

export function clipIsReady(generation: WebMusicGeneration, clip: WebMusicClip): boolean {
  return (
    Boolean(clip.ready || clip.audio_url) ||
    String(generation.status).toLowerCase() === "success"
  );
}

export function generationIsInstrumental(generation: WebMusicGeneration): boolean {
  const lyrics = String(generation.lyrics || "").trim().toLowerCase();
  return Boolean(generation.instrumental) || !lyrics || lyrics === "[instrumental]";
}

export function clipDownloadUrl(
  songId: string,
  variant: string,
  kind: ClipDownloadKind
): string {
  const base = `/api/v3/web-music/generations/${encodeURIComponent(songId)}`;
  if (kind === "mp3") return `${base}/download?variant=${encodeURIComponent(variant)}`;
  if (kind === "wav") return `${base}/download-wav?variant=${encodeURIComponent(variant)}`;
  return `${base}/timed-lyrics?variant=${encodeURIComponent(variant)}&format=${kind}`;
}

export function formatClipDuration(seconds?: number | null): string {
  const total = Math.round(Number(seconds) || 0);
  if (total <= 0) return "";
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function percent(value?: number | null): string {
  return `${Math.round((value ?? 0.5) * 100)}%`;
}

export function vocalLabel(value?: string | null): string {
  if (value === "f") return "Female";
  if (value === "m") return "Male";
  if (value === "both") return "Both";
  return "Not set";
}

export function statusClass(status: string): "ok" | "err" | "live" {
  const value = status.toLowerCase();
  if (value === "success" || value === "ready" || value === "completed") return "ok";
  if (value === "failed" || value === "error") return "err";
  return "live";
}

export function dayLabel(value: number): string {
  if (!value) return "Earlier";
  const date = new Date(value);
  const today = new Date();
  const day = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  if (value >= day) return "Today";
  if (value >= day - 86_400_000) return "Yesterday";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function timeAgo(value?: string | null): string {
  if (!value) return "";
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "";
  const minutes = Math.floor((Date.now() - then) / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(then).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
