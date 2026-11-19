/** Shapes returned by `GET /progress`, `GET /settings` and the download queue. */

export interface ProgressRowMeta {
  batch_id: string;
  profile_id: string;
  role: string;
  run_dir?: string | null;
  source_mode?: string | null;
  background_16x9_path?: string | null;
  background_9x16_path?: string | null;
  thumbnail_16x9_path?: string | null;
  thumbnail_9x16_path?: string | null;
  expected?: number;
  saved?: number;
  download_pending?: number;
  download_ready?: number;
  bg_ready?: number;
  bg_total?: number;
  th_ready?: number;
  th_total?: number;
  bg_status?: string;
  th_status?: string;
  youtube_status?: string;
  youtube_url?: string | null;
  youtube_success?: number;
  youtube_pending?: number;
  youtube_failed?: number;
  long_ready?: boolean;
  reel_ready?: boolean;
  pipeline_complete?: boolean;
  auto_upload_youtube?: boolean | null;
  music_started_at?: string | null;
  music_updated_at?: string | null;
  image_started_at?: string | null;
  image_updated_at?: string | null;
  youtube_created_at?: string | null;
  youtube_updated_at?: string | null;
  updated_at?: string | null;
  draft_failed_song_ids?: string[];
  suno_failed_song_ids?: string[];
}

export interface ProgressRow {
  batch: string;
  run_date: string;
  channel: string;
  album?: string | null;
  status: string;
  music: string;
  image: string;
  converter: string;
  merge: string;
  youtube: string;
  stage: string;
  notes: string;
  updated: string;
  meta: ProgressRowMeta;
}

export interface ProgressListResponse {
  rows: ProgressRow[];
  summary?: string;
  updated_at?: string | null;
}

export interface ProgressSettings {
  imageSourceMode?: string | null;
  sunoOutputDir?: string | null;
  downloadsDir?: string | null;
  [key: string]: unknown;
}

export interface PendingDownloadTarget {
  download_url?: string | null;
  downloaded?: boolean;
  output_dir?: string | null;
  target_path?: string | null;
}

export interface PendingDownloadItem {
  task_id: string;
  song_id?: string | null;
  batch_id?: string | null;
  title?: string | null;
  track_number?: number | null;
  primary?: PendingDownloadTarget;
  secondary?: PendingDownloadTarget;
}

export interface PendingDownloadsResponse {
  items?: PendingDownloadItem[];
}

export interface ImageJobsSyncManualResponse {
  updated?: number;
}

export interface ImageJobsRetryResponse {
  updated?: number;
}
