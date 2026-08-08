export type PipelineStage =
  | 'Music'
  | 'Image'
  | 'Converter'
  | 'Export'
  | 'Merge'
  | 'YouTube'
  | 'Streaming'
  | 'Done'
  | 'Completed'
  | 'Error'
  | string;

export interface AdminPipelineCounts {
  active: number;
  failed: number;
  stuck: number;
  total: number;
}

export interface AdminPipelineBoardRow {
  user_id: string;
  user_email: string;
  user_display_name: string;
  batch_id: string;
  role: string;
  profile_id: string;
  profile_name: string;
  album: string | null;
  run_date: string;
  stage: PipelineStage;
  status: string;
  music: string;
  image: string;
  converter: string;
  merge: string;
  youtube: string;
  streaming: string;
  notes: string;
  error_snippet: string | null;
  updated: string;
  updated_at: string | null;
  age_seconds: number | null;
  draft_failed_count: number;
  suno_failed_count: number;
  meta: Record<string, unknown>;
}

export interface AdminPipelineBoardResponse {
  rows: AdminPipelineBoardRow[];
  summary: string;
  updated_at: string;
  counts: AdminPipelineCounts;
}

export interface AdminPipelineRetryCosts {
  updated_at?: string | null;
  draft_credits_min?: number | null;
  draft_credits_max?: number | null;
  suno_credits?: number | null;
  background_image_credits?: number | null;
  thumbnail_image_credits?: number | null;
  operations?: Record<string, number | null | undefined>;
  disclaimer?: string;
}

export interface AdminPipelineSong {
  id: string;
  batch_index: number;
  title: string | null;
  album: string | null;
  status: string;
  updated_at: string | null;
  suno_status: string | null;
  suno_error: string | null;
  suno_updated_at: string | null;
}

export interface AdminPipelineImageJob {
  id: string;
  profile_id: string | null;
  channel_role: string | null;
  kind: string;
  status: string;
  provider?: string | null;
  prompt_length?: number | null;
  attempt_count: number;
  error: string | null;
  updated_at: string | null;
}

export interface AdminPipelineYoutubeJob {
  id: string;
  profile_id: string | null;
  role: string | null;
  status: string;
  youtube_video_id: string | null;
  youtube_url: string | null;
  error_message: string | null;
  updated_at: string | null;
}

export interface AdminPipelineStreamingJob {
  id: string;
  song_id: string | null;
  batch_id?: string | null;
  album_id?: string | null;
  kind: string;
  status: string;
  attempt_count: number;
  error: string | null;
  source_url?: string | null;
  storage_key: string | null;
  song_title?: string | null;
  song_album?: string | null;
  song_batch_index?: number | null;
  stream_album_name?: string | null;
  stream_channel_role?: string | null;
  stream_album_publish_status?: string | null;
  stream_track_publish_status?: string | null;
  stream_track_variant?: string | null;
  created_at?: string | null;
  updated_at: string | null;
}

export interface AdminPipelineBatchDetail {
  batch_id: string;
  user_id: string;
  user_email: string;
  user_display_name: string;
  status: string;
  song_count: number;
  ok_profile_id: string | null;
  alt_profile_id: string | null;
  ok_album: string | null;
  alt_album: string | null;
  created_at: string | null;
  updated_at: string | null;
  songs: AdminPipelineSong[];
  image_jobs: AdminPipelineImageJob[];
  youtube_jobs: AdminPipelineYoutubeJob[];
  streaming_jobs: AdminPipelineStreamingJob[];
}

export interface PipelineBoardParams {
  limit?: number;
  active_only?: boolean;
  stage?: string;
  user_id?: string;
  q?: string;
}
