"use client";

import { platformJson } from "@/lib/auth-fetch";

export type SunoDownloadTarget = {
  download_url: string | null;
  downloaded: boolean;
  output_dir: string | null;
  target_path: string | null;
};

export type PendingMusicDownloadItem = {
  task_id: string;
  song_id: string | null;
  batch_id: string | null;
  title: string | null;
  track_number: number | null;
  primary: SunoDownloadTarget;
  secondary: SunoDownloadTarget;
};

export type PendingMusicDownloadsResponse = {
  items: PendingMusicDownloadItem[];
};

export async function getPendingMusicDownloads(limit = 20): Promise<PendingMusicDownloadsResponse> {
  return platformJson<PendingMusicDownloadsResponse>({
    path: `/music/downloads/pending?limit=${encodeURIComponent(String(limit))}`,
    method: "GET",
  });
}
