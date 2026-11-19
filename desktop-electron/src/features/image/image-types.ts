export interface ImageJobListItem {
  id: string;
  batch_id: string | null;
  song_id: string | null;
  profile_id: string | null;
  kind: string;
  channel_role: string;
  prompt: string | null;
  provider?: string | null;
  resolution?: string;
  status: string;
  attempt_count?: number;
  input_image_path: string | null;
  style_reference_path: string | null;
  output_image_path: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface MusicHistorySong {
  album?: string | null;
  title?: string | null;
}

export interface MusicHistoryBatch {
  batch_id: string;
  status: string;
  song_count: number;
  from_date?: string | null;
  to_date?: string | null;
  ok_album?: string | null;
  alt_album?: string | null;
  created_at: string;
  updated_at: string;
  songs?: MusicHistorySong[];
}

export interface MusicHistoryResponse {
  batches?: MusicHistoryBatch[];
  summary?: string;
  updated_at?: string;
}

export interface ChannelProfile {
  id: string;
  name: string;
  folder_name?: string;
  run_prefix?: string;
  image_config?: Record<string, unknown>;
}

export interface ImageSettings {
  imageBackgroundPrompt?: unknown;
  imageThumbnailPrompt?: unknown;
  imagePrompt?: unknown;
  [key: string]: unknown;
}

export interface ImageWorkspaceData {
  imageJobs: ImageJobListItem[];
  batches: MusicHistoryBatch[];
  profiles: ChannelProfile[];
  settings: ImageSettings;
  /** True when the batch metadata endpoint failed and dates are derived from jobs. */
  batchesUnavailable: boolean;
  /** True when the prompts endpoint failed; the editor stays usable. */
  settingsUnavailable: boolean;
}
