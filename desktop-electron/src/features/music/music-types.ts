/**
 * Wire types for the Music workspace.
 *
 * Shapes mirror the live `platform_api` OpenAPI document. Optional fields stay
 * optional so a partial response degrades instead of throwing.
 */

export interface MusicUser {
  id: string;
  email?: string;
  display_name?: string;
  credit_balance?: number;
  plan_name?: string | null;
  channel_profile_count?: number;
}

export interface ChannelProfile {
  id: string;
  name: string;
  folder_name?: string | null;
  run_prefix?: string | null;
  output_resolution?: string;
  image_config?: Record<string, unknown> | null;
  created_at?: string;
  updated_at?: string;
}

export interface PromptOption {
  id: string;
  name: string;
}

export type SettingsRecord = Record<string, unknown>;

export interface OperationCost {
  operation_type: string;
  credits_per_operation?: number | null;
  available?: boolean;
  message?: string | null;
}

export interface MusicHistorySong {
  song_id: string;
  batch_index: number;
  title?: string | null;
  album?: string | null;
  lyrics?: string | null;
  description_id?: string | null;
  description_name?: string | null;
  structure_id?: string | null;
  structure_name?: string | null;
  mood_id?: string | null;
  mood_name?: string | null;
  output_dir_ok?: string | null;
  output_dir_alt?: string | null;
  status?: string;
  suno_status?: string | null;
  suno_error_message?: string | null;
  youtube_status?: string | null;
  downloaded_ok?: boolean;
  downloaded_alt?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface MusicHistoryBatch {
  batch_id: string;
  status?: string;
  song_count?: number;
  from_date?: string | null;
  to_date?: string | null;
  planned_days?: number;
  ok_profile_id?: string | null;
  ok_profile_name?: string | null;
  alt_profile_id?: string | null;
  alt_profile_name?: string | null;
  ok_album?: string | null;
  alt_album?: string | null;
  created_at?: string;
  updated_at?: string;
  songs?: MusicHistorySong[];
}

export interface MusicHistoryResponse {
  batches?: MusicHistoryBatch[];
  summary?: string;
  updated_at?: string;
}

export interface BatchCreatePayload {
  ok_profile_id: string;
  alt_profile_id: string;
  description_id: string | null;
  structure_id: string | null;
  mood_id: string | null;
  structure_mode: "template" | "ai_free" | "suno";
  shuffle_structure: boolean;
  shuffle_mood: boolean;
  auto_gen_image: boolean;
  auto_gsuno: boolean;
  auto_video_after_suno: boolean;
  auto_merge_after_video: boolean;
  auto_reel_after_video: boolean;
  auto_upload_youtube: boolean;
  song_count: number;
  language: string;
  secondary_language: string | null;
  creativity_level: number;
  pairing_mode: "match_key";
  from_date: string;
  to_date: string;
  ok_run_dir: string | null;
  alt_run_dir: string | null;
}

export interface BatchCreateResponse {
  batch_id: string;
  status: string;
  song_count: number;
  from_date: string;
  to_date: string;
  planned_days: number;
  ok_run_dir?: string | null;
  alt_run_dir?: string | null;
}

export interface BatchStatusResponse {
  batch_id: string;
  status: string;
  total_songs: number;
  drafts_completed: number;
  drafts_failed: number;
  suno_submitted: number;
  suno_completed: number;
  suno_failed: number;
  audio_downloaded: number;
  images_completed: number;
  ok_run_dir?: string | null;
  alt_run_dir?: string | null;
}

export interface DraftResponse {
  title: string;
  album: string;
  lyrics: string;
}

export interface PolishResponse {
  lyrics: string;
  suno_queued?: boolean;
}

export interface ClaimedPoolItem {
  id: number;
  text: string;
  secondary_text?: string | null;
  reservation_token: string;
}

export interface ClaimPoolResponse {
  kind: "titles" | "albums" | "openings";
  item: ClaimedPoolItem;
}

export interface DraftSeeds {
  titleSeed: string;
  albumSeed: string;
  openingSeed: string | null;
}

export interface ComposerState {
  fromDate: string;
  toDate: string;
  primaryIds: string[];
  secondaryIds: string[];
  title: string;
  album: string;
  lyrics: string;
}

export interface HistoryFilters {
  fromDate: string;
  toDate: string;
  lastBatchOnly: boolean;
}

export interface MusicWorkspaceData {
  me: MusicUser | null;
  profiles: ChannelProfile[];
  settings: SettingsRecord;
  descriptions: PromptOption[];
  structures: PromptOption[];
  history: MusicHistoryResponse;
  costs: OperationCost[];
}

export type SaveStatus = "idle" | "saving" | "saved" | "error";
