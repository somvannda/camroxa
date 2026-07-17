"use client";

import { platformJson } from "@/lib/auth-fetch";

export type MusicHistorySong = {
  song_id: string;
  batch_index: number;
  title: string | null;
  album: string | null;
  lyrics: string | null;
  description_id: string | null;
  description_name: string | null;
  structure_id: string | null;
  structure_name: string | null;
  output_dir_ok: string | null;
  output_dir_alt: string | null;
  status: string;
  suno_status: string | null;
  youtube_status: string | null;
  downloaded_ok: boolean;
  downloaded_alt: boolean;
  image_jobs_completed: number;
  image_jobs_total: number;
  created_at: string;
  updated_at: string;
};

export type MusicHistoryBatch = {
  batch_id: string;
  status: string;
  song_count: number;
  from_date: string | null;
  to_date: string | null;
  planned_days: number;
  ok_profile_id: string | null;
  ok_profile_name: string | null;
  alt_profile_id: string | null;
  alt_profile_name: string | null;
  created_at: string;
  updated_at: string;
  songs: MusicHistorySong[];
};

export type MusicHistoryResponse = {
  batches: MusicHistoryBatch[];
  summary: string;
  updated_at: string;
};

export async function getMusicHistory(limit = 4): Promise<MusicHistoryResponse> {
  return platformJson<MusicHistoryResponse>({
    path: `/music/history?limit=${encodeURIComponent(String(limit))}`,
    method: "GET",
  });
}
