import { platformRequest } from '@/shared/api/platformClient'

export type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export type UserMeResponse = {
  id: string
  email: string
  email_confirmed: boolean
  display_name: string
  credit_balance: number
  plan_name: string | null
  profile_allowance: number | null
  channel_profile_count: number
}

export type ProfileResponse = {
  id: string
  user_id: string
  name: string
  folder_name?: string | null
  run_prefix?: string | null
  logo_path?: string | null
  video_template_id?: string | null
  reel_template_id?: string | null
  output_resolution: string
  image_config: Record<string, unknown>
  youtube_config: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export type CreateProfileRequest = {
  name: string
  folder_name?: string | null
  run_prefix?: string | null
  logo_path?: string | null
  logo_base64?: string | null
  cover_images?: string[]
  video_template_id?: string | null
  reel_template_id?: string | null
  output_resolution?: string
  image_config?: Record<string, unknown>
  youtube_config?: Record<string, unknown>
}

export type UpdateProfileRequest = {
  name?: string
  folder_name?: string | null
  run_prefix?: string | null
  logo_path?: string | null
  logo_base64?: string | null
  cover_images?: string[]
  video_template_id?: string | null
  reel_template_id?: string | null
  output_resolution?: string | null
  image_config?: Record<string, unknown>
  youtube_config?: Record<string, unknown>
}

export type ValidateLicenseResponse = {
  plan_type: string
  profile_allowance: number
  monthly_song_quota: number | null
  songs_remaining: number | null
  wallet_balance: number
  expiration_date: string | null
}

export type DailyUsageResponse = {
  date: string
  songs: number
  images: number
  videos: number
}

export type RecentActivityResponse = {
  timestamp: string
  kind: string
  detail: string
  status: string
}

export type DashboardStatsResponse = {
  credits_spent: number
  credits_remaining: number
  credits_total: number
  songs_generated: number
  songs_remaining: number | null
  songs_quota: number | null
  images_generated: number
  videos_generated: number
  usage_by_day: DailyUsageResponse[]
  recent_activity: RecentActivityResponse[]
}

export type ProgressRowMetaResponse = {
  batch_id: string
  profile_id: string
  role: string
  run_dir: string | null
  source_mode: string | null
  background_16x9_path: string | null
  background_9x16_path: string | null
  thumbnail_16x9_path: string | null
  thumbnail_9x16_path: string | null
  long_ready: boolean
  reel_ready: boolean
  expected: number
  saved: number
  download_ready: number
  download_pending: number
  bg_ready: number
  bg_total: number
  th_ready: number
  th_total: number
  bg_status: string
  th_status: string
  youtube_status: string
  youtube_url: string | null
  youtube_success: number
  youtube_pending: number
  youtube_failed: number
  music_started_at: string | null
  music_updated_at: string | null
  image_started_at: string | null
  image_updated_at: string | null
  youtube_created_at: string | null
  youtube_updated_at: string | null
}

export type ProgressRowResponse = {
  batch: string
  run_date: string
  channel: string
  status: string
  music: string
  image: string
  converter: string
  merge: string
  youtube: string
  stage: string
  notes: string
  updated: string
  meta: ProgressRowMetaResponse
}

export type ProgressListResponse = {
  rows: ProgressRowResponse[]
  summary: string
  updated_at: string
}

export type UserSettingsResponse = Record<string, unknown>

export type VerificationResponse = {
  message: string
  email: string
  is_verified: boolean
}

export type PromptNameOption = {
  id: string
  name: string
  is_owned?: boolean
}

export type PublicDescriptionResponse = PromptNameOption & {
  match_key: string | null
}

export type UserOwnedPrompt = {
  id: string
  name: string
  content: string
  created_at: string
  updated_at: string
}

export type WorkspacePromptOption = {
  id: string
  name: string
  match_key?: string | null
  is_owned: boolean
}

export type PromptUsageByUser = {
  user_id: string
  user_email: string
  user_display_name: string
  usage_count: number
  last_used_at: string | null
}

export type PromptUsageResponse = {
  prompt_id: string
  prompt_name: string
  owner_label: string
  usage_count: number
  users: PromptUsageByUser[]
}

export type GenerateNamesResponse = {
  names: string[]
}

export type GenerateImageResponse = {
  image_base64: string
  width: number
  height: number
}

export type ImageGenerationRequest = {
  prompt: string
  provider: 'fal' | 'slai' | 'openai' | 'cala'
  resolution: string
  style_strength: number
  base_image?: string | null
  channel_profile_id?: string | null
}

export type ImageGenerationResponse = {
  image_base64: string
}

export type GenerateCoversResponse = {
  images: string[]
}

export type GenerateDescriptionTextResponse = {
  description: string
}

export type GenerateKeywordsResponse = {
  keywords: string[]
}

export type GenerateTagsResponse = {
  tags: string[]
}

export type CreateProfileResponse = {
  profile_id: string
  name: string
  message: string
}

export type DraftGenerationRequest = {
  language: string
  creativity_level: number
  description?: string | null
  structure?: string | null
  description_id?: string | null
  structure_id?: string | null
  avoid_titles?: string[]
  avoid_albums?: string[]
  avoid_openings?: string[]
  forced_title?: string | null
  forced_album?: string | null
  forced_opening?: string | null
  title_seed?: string | null
  album_seed?: string | null
  channel_profile_id?: string | null
}

export type DraftGenerationResponse = {
  title: string
  album: string
  lyrics: string
}

export type LyricsPolishRequest = {
  lyrics: string
  strength: number
  channel_profile_id?: string | null
}

export type LyricsPolishResponse = {
  lyrics: string
}

export type BatchCreateRequest = {
  ok_profile_id: string
  alt_profile_id: string
  description_id?: string | null
  structure_id?: string | null
  auto_gen_image?: boolean
  auto_gsuno?: boolean
  song_count: number
  language: string
  creativity_level: number
  pairing_mode: string
  from_date: string
  to_date: string
  ok_run_dir?: string | null
  alt_run_dir?: string | null
  album?: string | null
}

export type OperationCostResponse = {
  operation_type: string
  provider: string | null
  sub_model: string | null
  credits_per_operation: number | null
  available: boolean
  message: string | null
}

export type OperationCostsResponse = {
  items: OperationCostResponse[]
}

export type BatchCreateResponse = {
  batch_id: string
  status: string
  song_count: number
  from_date: string
  to_date: string
  planned_days: number
  ok_run_dir: string | null
  alt_run_dir: string | null
}

export type BatchStatusResponse = {
  batch_id: string
  status: string
  total_songs: number
  drafts_completed: number
  drafts_failed: number
  suno_submitted: number
  suno_completed: number
  suno_failed: number
  audio_downloaded: number
  images_completed: number
}

export type ImageJobListItem = {
  id: string
  batch_id: string | null
  song_id: string | null
  profile_id: string | null
  kind: 'background' | 'thumbnail'
  channel_role: 'ok' | 'alt'
  prompt: string | null
  provider: string | null
  resolution: string
  style_strength: number
  input_image_path: string | null
  style_reference_path: string | null
  source_job_id: string | null
  status: 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
  attempt_count: number
  output_image_path: string | null
  error: string | null
  created_at: string
  updated_at: string
}

export type ImageJobsListResponse = {
  items: ImageJobListItem[]
}

export type ImageJobsEnqueueRequest = {
  batch_ids: string[]
}

export type ImageJobsEnqueueResponse = {
  created: number
}

export type ImageJobsRunRequest = {
  batch_id?: string | null
  limit?: number
}

export type ImageJobsRunResponse = {
  scheduled: number
}

export type ImageJobsRetryRequest = {
  job_ids?: string[] | null
  batch_id?: string | null
}

export type ImageJobsRetryResponse = {
  updated: number
}

export type ImageJobsClearRequest = {
  batch_id?: string | null
  statuses?: string[] | null
}

export type ImageJobsClearResponse = {
  deleted: number
}

export type ImageJobsSyncManualRequest = {
  batch_id: string
}

export type ImageJobsSyncManualResponse = {
  updated: number
}

export type ImageSamplePackItem = {
  id: string
  category: string
  name: string
  source_type: string
  source_value: string
  version_label: string | null
  notes: string | null
}

export type ImageSamplePackListResponse = {
  items: ImageSamplePackItem[]
}

export type MusicHistorySongResponse = {
  song_id: string
  batch_index: number
  title: string | null
  album: string | null
  lyrics: string | null
  description_id: string | null
  description_name: string | null
  structure_id: string | null
  structure_name: string | null
  output_dir_ok: string | null
  output_dir_alt: string | null
  status: string
  suno_status: string | null
  youtube_status: string | null
  downloaded_ok: boolean
  downloaded_alt: boolean
  image_jobs_completed: number
  image_jobs_total: number
  created_at: string
  updated_at: string
}

export type MusicHistoryBatchResponse = {
  batch_id: string
  status: string
  song_count: number
  from_date: string | null
  to_date: string | null
  planned_days: number
  ok_profile_id: string | null
  ok_profile_name: string | null
  alt_profile_id: string | null
  alt_profile_name: string | null
  created_at: string
  updated_at: string
  songs: MusicHistorySongResponse[]
}

export type MusicHistoryListResponse = {
  batches: MusicHistoryBatchResponse[]
  summary: string
  updated_at: string
}

export type PendingMusicDownloadTargetResponse = {
  download_url: string | null
  downloaded: boolean
  output_dir: string | null
  target_path: string | null
}

export type PendingMusicDownloadItemResponse = {
  task_id: string
  song_id: string | null
  batch_id: string | null
  title: string | null
  track_number: number | null
  primary: PendingMusicDownloadTargetResponse
  secondary: PendingMusicDownloadTargetResponse
}

export type PendingMusicDownloadsResponse = {
  items: PendingMusicDownloadItemResponse[]
}

export type MusicDownloadSyncItemRequest = {
  task_id: string
  downloaded_primary?: boolean
  downloaded_secondary?: boolean
  output_dir_primary?: string | null
  output_dir_secondary?: string | null
}

export type MusicDownloadSyncResponse = {
  updated: number
}

export type YouTubeConnectionChannelOption = {
  id: string
  title: string
}

export type YouTubeConnectionResponse = {
  profile_id: string
  profile_name: string
  status: 'not_connected' | 'pending_browser' | 'awaiting_channel_selection' | 'connected' | 'error'
  channel_id: string | null
  channel_title: string | null
  session_id: string | null
  channels: YouTubeConnectionChannelOption[]
  message: string | null
}

export type YouTubeConnectionsResponse = {
  connections: YouTubeConnectionResponse[]
}

export type YouTubePlaylistOption = {
  id: string
  title: string
}

export type YouTubePlaylistsResponse = {
  playlists: YouTubePlaylistOption[]
}

export type EnqueueYouTubeMergeUploadRequest = {
  batch_id: string
  role: string
  merged_mp4_path: string
}

export type EnqueueYouTubeMergeUploadResponse = {
  job_uid: string
  status: string
  profile_id: string
  batch_id: string
  role: string
  file_path: string
  message: string
  blocked_reason: string | null
}

export type RunYouTubeUploadsRequest = {
  batch_id?: string | null
  limit?: number
}

export type RunYouTubeUploadsResponse = {
  scheduled: number
}

export type ContentPoolKind = 'titles' | 'albums' | 'openings'

export type ContentPoolStat = {
  total: number
  unused: number
}

export type ContentPoolStatsResponse = {
  titles: ContentPoolStat
  albums: ContentPoolStat
  openings: ContentPoolStat
}

export type ContentPoolRow = {
  id: number
  text: string
  secondary_text: string | null
  used_count: number
  created_at: string | null
}

export type ContentPoolListResponse = {
  kind: ContentPoolKind
  total: number
  limit: number
  offset: number
  items: ContentPoolRow[]
}

export type ClaimContentPoolRequest = {
  reservation_token?: string | null
  consumer?: string
  limit?: number
  ttl_seconds?: number
}

export type ClaimedContentPoolItem = {
  id: number
  text: string
  secondary_text: string | null
  used_count: number
  reservation_token: string
  reserved_by: string
  reserved_at: string | null
  created_at: string | null
}

export type ClaimContentPoolResponse = {
  kind: ContentPoolKind
  item: ClaimedContentPoolItem
}

export type ReservationActionRequest = {
  item_id: number
  reservation_token: string
}

export type ReservationActionResponse = {
  ok: boolean
}

export type StartYouTubeConnectionResponse = {
  session_id: string
  auth_url: string
  status: string
}

export async function apiLogin(input: { email: string; password: string }): Promise<TokenResponse> {
  return platformRequest<TokenResponse>('/auth/login', { method: 'POST', body: input })
}

export async function apiRegister(input: {
  email: string
  password: string
  display_name: string
}): Promise<{ id: string; email: string; display_name: string }> {
  return platformRequest('/auth/register', { method: 'POST', body: input })
}

export async function apiRefresh(input: { refresh_token: string }): Promise<TokenResponse> {
  return platformRequest<TokenResponse>('/auth/refresh', { method: 'POST', body: input })
}

export async function apiLogout(): Promise<{ message: string }> {
  return platformRequest<{ message: string }>('/auth/logout', { method: 'POST', auth: true })
}

export async function apiGetMe(): Promise<UserMeResponse> {
  return platformRequest<UserMeResponse>('/users/me', { auth: true })
}

export async function apiListProfiles(): Promise<ProfileResponse[]> {
  return platformRequest<ProfileResponse[]>('/profiles', { auth: true })
}

export async function apiCreateUserProfile(input: CreateProfileRequest): Promise<ProfileResponse> {
  return platformRequest<ProfileResponse>('/profiles', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiUpdateUserProfile(profileId: string, input: UpdateProfileRequest): Promise<ProfileResponse> {
  return platformRequest<ProfileResponse>(`/profiles/${profileId}`, {
    method: 'PUT',
    body: input,
    auth: true,
  })
}

export async function apiDeleteUserProfile(profileId: string): Promise<{ message: string }> {
  return platformRequest<{ message: string }>(`/profiles/${profileId}`, {
    method: 'DELETE',
    auth: true,
  })
}

export async function apiValidateLicense(): Promise<ValidateLicenseResponse> {
  return platformRequest<ValidateLicenseResponse>('/licenses/validate', { auth: true })
}

export async function apiGetDashboardStats(): Promise<DashboardStatsResponse> {
  return platformRequest<DashboardStatsResponse>('/stats/dashboard', { auth: true })
}

export async function apiListProgressRows(input: {
  limit: number
  active_only: boolean
  from_date?: string
  to_date?: string
}): Promise<ProgressListResponse> {
  const params = new URLSearchParams()
  params.set('limit', String(input.limit))
  params.set('active_only', String(input.active_only))
  if (input.from_date) {
    params.set('from_date', input.from_date)
  }
  if (input.to_date) {
    params.set('to_date', input.to_date)
  }

  return platformRequest<ProgressListResponse>(`/progress?${params.toString()}`, { auth: true })
}

export async function apiGetSettings(): Promise<UserSettingsResponse> {
  return platformRequest<UserSettingsResponse>('/settings', { auth: true })
}

export async function apiPatchSettings(input: Record<string, unknown>): Promise<UserSettingsResponse> {
  return platformRequest<UserSettingsResponse>('/settings', {
    method: 'PATCH',
    body: input,
    auth: true,
  })
}

export async function apiSendVerification(input: { email: string }): Promise<VerificationResponse> {
  return platformRequest<VerificationResponse>('/auth/send-verification', { method: 'POST', body: input })
}

export async function apiVerifyEmail(input: { email: string; code: string }): Promise<VerificationResponse> {
  return platformRequest<VerificationResponse>('/auth/verify-email', { method: 'POST', body: input })
}

export async function apiListPromptDescriptionNames(): Promise<PromptNameOption[]> {
  const items = await platformRequest<WorkspacePromptOption[]>('/prompts/descriptions/workspace', {
    auth: true,
  })
  return items.map((item) => ({ id: item.id, name: item.name, is_owned: item.is_owned }))
}

export async function apiListPromptStructureNames(): Promise<PromptNameOption[]> {
  const items = await platformRequest<WorkspacePromptOption[]>('/prompts/structures/workspace', {
    auth: true,
  })
  return items.map((item) => ({ id: item.id, name: item.name, is_owned: item.is_owned }))
}

export async function apiListMyDescriptions(): Promise<UserOwnedPrompt[]> {
  return platformRequest<UserOwnedPrompt[]>('/prompts/me/descriptions', { auth: true })
}

export async function apiListMyStructures(): Promise<UserOwnedPrompt[]> {
  return platformRequest<UserOwnedPrompt[]>('/prompts/me/structures', { auth: true })
}

export async function apiCreateMyDescription(input: {
  name: string
  content: string
}): Promise<UserOwnedPrompt> {
  return platformRequest<UserOwnedPrompt>('/prompts/me/descriptions', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiUpdateMyDescription(
  id: string,
  input: { name: string; content: string },
): Promise<UserOwnedPrompt> {
  return platformRequest<UserOwnedPrompt>(`/prompts/me/descriptions/${id}`, {
    method: 'PUT',
    body: input,
    auth: true,
  })
}

export async function apiDeleteMyDescription(id: string): Promise<{ message: string }> {
  return platformRequest<{ message: string }>(`/prompts/me/descriptions/${id}`, {
    method: 'DELETE',
    auth: true,
  })
}

export async function apiCreateMyStructure(input: {
  name: string
  content: string
}): Promise<UserOwnedPrompt> {
  return platformRequest<UserOwnedPrompt>('/prompts/me/structures', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiUpdateMyStructure(
  id: string,
  input: { name: string; content: string },
): Promise<UserOwnedPrompt> {
  return platformRequest<UserOwnedPrompt>(`/prompts/me/structures/${id}`, {
    method: 'PUT',
    body: input,
    auth: true,
  })
}

export async function apiDeleteMyStructure(id: string): Promise<{ message: string }> {
  return platformRequest<{ message: string }>(`/prompts/me/structures/${id}`, {
    method: 'DELETE',
    auth: true,
  })
}

export async function apiListPublicGenres(): Promise<PublicDescriptionResponse[]> {
  return platformRequest<PublicDescriptionResponse[]>('/prompts/descriptions/public')
}

export async function apiGenerateDraft(input: DraftGenerationRequest): Promise<DraftGenerationResponse> {
  return platformRequest<DraftGenerationResponse>('/generation/draft', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiPolishLyrics(input: LyricsPolishRequest): Promise<LyricsPolishResponse> {
  return platformRequest<LyricsPolishResponse>('/generation/polish-lyrics', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiCreateBatch(input: BatchCreateRequest): Promise<BatchCreateResponse> {
  return platformRequest<BatchCreateResponse>('/batches', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiGetOperationCosts(): Promise<OperationCostsResponse> {
  return platformRequest<OperationCostsResponse>('/credits/operation-costs', { auth: true })
}

export async function apiGetBatchStatus(batchId: string): Promise<BatchStatusResponse> {
  return platformRequest<BatchStatusResponse>(`/batches/${batchId}`, { auth: true })
}

export async function apiListMusicHistory(input?: { limit?: number }): Promise<MusicHistoryListResponse> {
  const params = new URLSearchParams()
  params.set('limit', String(input?.limit ?? 8))
  return platformRequest<MusicHistoryListResponse>(`/music/history?${params.toString()}`, { auth: true })
}

export async function apiListPendingMusicDownloads(input?: { limit?: number }): Promise<PendingMusicDownloadsResponse> {
  const params = new URLSearchParams()
  params.set('limit', String(input?.limit ?? 20))
  return platformRequest<PendingMusicDownloadsResponse>(`/music/downloads/pending?${params.toString()}`, { auth: true })
}

export async function apiSyncMusicDownloads(
  items: MusicDownloadSyncItemRequest[],
): Promise<MusicDownloadSyncResponse> {
  return platformRequest<MusicDownloadSyncResponse>('/music/downloads/sync', {
    method: 'POST',
    body: { items },
    auth: true,
  })
}

export async function apiListYouTubeConnections(): Promise<YouTubeConnectionResponse[]> {
  const response = await platformRequest<YouTubeConnectionsResponse>('/youtube/connections', { auth: true })
  return response.connections
}

export async function apiStartYouTubeConnection(profileId: string): Promise<StartYouTubeConnectionResponse> {
  return platformRequest<StartYouTubeConnectionResponse>(`/youtube/profiles/${profileId}/connect`, {
    method: 'POST',
    auth: true,
  })
}

export async function apiSelectYouTubeChannel(
  sessionId: string,
  channelId: string,
): Promise<YouTubeConnectionResponse> {
  return platformRequest<YouTubeConnectionResponse>(`/youtube/connect-sessions/${sessionId}/select-channel`, {
    method: 'POST',
    body: { channel_id: channelId },
    auth: true,
  })
}

export async function apiDisconnectYouTubeConnection(profileId: string): Promise<{ message: string }> {
  return platformRequest<{ message: string }>(`/youtube/profiles/${profileId}/connection`, {
    method: 'DELETE',
    auth: true,
  })
}

export async function apiResyncYouTubeConnection(profileId: string): Promise<YouTubeConnectionResponse> {
  return platformRequest<YouTubeConnectionResponse>(`/youtube/profiles/${profileId}/resync`, {
    method: 'POST',
    auth: true,
  })
}

export async function apiListYouTubePlaylists(profileId: string): Promise<YouTubePlaylistsResponse> {
  return platformRequest<YouTubePlaylistsResponse>(`/youtube/profiles/${profileId}/playlists`, {
    method: 'GET',
    auth: true,
  })
}

export async function apiEnqueueYouTubeMergeUpload(
  profileId: string,
  input: EnqueueYouTubeMergeUploadRequest,
): Promise<EnqueueYouTubeMergeUploadResponse> {
  return platformRequest<EnqueueYouTubeMergeUploadResponse>(`/youtube/profiles/${profileId}/uploads/merge`, {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiRunYouTubeUploads(input: RunYouTubeUploadsRequest = {}): Promise<RunYouTubeUploadsResponse> {
  return platformRequest<RunYouTubeUploadsResponse>('/youtube/uploads/run', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiGetContentPoolStats(): Promise<ContentPoolStatsResponse> {
  return platformRequest<ContentPoolStatsResponse>('/content-pools/stats', { auth: true })
}

export async function apiListContentPoolItems(
  kind: ContentPoolKind,
  input: { limit?: number; offset?: number } = {},
): Promise<ContentPoolListResponse> {
  const params = new URLSearchParams()
  params.set('limit', String(input?.limit ?? 100))
  params.set('offset', String(input?.offset ?? 0))
  return platformRequest<ContentPoolListResponse>(`/content-pools/${kind}?${params.toString()}`, { auth: true })
}


export async function apiClaimContentPoolItem(
  kind: ContentPoolKind,
  input: ClaimContentPoolRequest = {},
): Promise<ClaimContentPoolResponse> {
  return platformRequest<ClaimContentPoolResponse>(`/content-pools/${kind}/claim`, {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiReleaseContentPoolItem(
  kind: ContentPoolKind,
  input: ReservationActionRequest,
): Promise<ReservationActionResponse> {
  return platformRequest<ReservationActionResponse>(`/content-pools/${kind}/release`, {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiFinalizeContentPoolItem(
  kind: ContentPoolKind,
  input: ReservationActionRequest,
): Promise<ReservationActionResponse> {
  return platformRequest<ReservationActionResponse>(`/content-pools/${kind}/finalize`, {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiGenerateImage(input: ImageGenerationRequest): Promise<ImageGenerationResponse> {
  return platformRequest<ImageGenerationResponse>('/generation/image', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export type LocalVideoConsumeRequest = {
  operation_type: 'video' | 'video_merge'
  channel_profile_id?: string | null
  count?: number
  ref_id?: string | null
}

export type LocalVideoConsumeResponse = {
  operation_type: string
  billing: string
  charged_credit_units: number
  list_credit_units: number
  charge_key?: string | null
}

export async function apiConsumeLocalVideo(
  input: LocalVideoConsumeRequest,
): Promise<LocalVideoConsumeResponse> {
  return platformRequest<LocalVideoConsumeResponse>('/generation/video/consume', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiRefundLocalVideo(input: {
  operation_type: 'video' | 'video_merge'
  channel_profile_id?: string | null
  charged_credit_units?: number
  count?: number
  ref_id?: string | null
  reason?: string
}): Promise<{ status: string; operation_type: string }> {
  return platformRequest('/generation/video/refund', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiListImageJobs(input: {
  batch_id?: string
  status?: string[]
  limit?: number
} = {}): Promise<ImageJobsListResponse> {
  const params = new URLSearchParams()
  if (input.batch_id) {
    params.set('batch_id', input.batch_id)
  }
  if (input.limit != null) {
    params.set('limit', String(input.limit))
  }
  if (input.status?.length) {
    input.status.forEach((value) => params.append('status', value))
  }

  const query = params.toString()
  return platformRequest<ImageJobsListResponse>(`/image-jobs${query ? `?${query}` : ''}`, {
    method: 'GET',
    auth: true,
  })
}

export async function apiEnqueueImageJobs(input: ImageJobsEnqueueRequest): Promise<ImageJobsEnqueueResponse> {
  return platformRequest<ImageJobsEnqueueResponse>('/image-jobs/enqueue', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiRunImageJobs(input: ImageJobsRunRequest = {}): Promise<ImageJobsRunResponse> {
  return platformRequest<ImageJobsRunResponse>('/image-jobs/run', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiRetryImageJobs(input: ImageJobsRetryRequest): Promise<ImageJobsRetryResponse> {
  return platformRequest<ImageJobsRetryResponse>('/image-jobs/retry', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiClearImageJobs(input: ImageJobsClearRequest = {}): Promise<ImageJobsClearResponse> {
  return platformRequest<ImageJobsClearResponse>('/image-jobs/clear', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiSyncManualImageJobs(input: ImageJobsSyncManualRequest): Promise<ImageJobsSyncManualResponse> {
  return platformRequest<ImageJobsSyncManualResponse>('/image-jobs/sync-manual', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiListImageSamplePacks(): Promise<ImageSamplePackListResponse> {
  return platformRequest<ImageSamplePackListResponse>('/image-sample-packs', {
    method: 'GET',
    auth: true,
  })
}

export async function apiGenerateNames(input: {
  genre: string
  role: 'primary' | 'secondary' | 'both'
  description: string
  match_key: string
  count: number
}): Promise<GenerateNamesResponse> {
  return platformRequest<GenerateNamesResponse>('/channel-setup/generate-names', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiGenerateLogo(input: {
  channel_name: string
  genre: string
  role: 'primary' | 'secondary'
  match_key: string
}): Promise<GenerateImageResponse> {
  return platformRequest<GenerateImageResponse>('/channel-setup/generate-logo', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiGenerateCovers(input: {
  channel_name: string
  genre: string
  count: number
  role: 'primary' | 'secondary'
  match_key?: string
}): Promise<GenerateCoversResponse> {
  return platformRequest<GenerateCoversResponse>('/channel-setup/generate-covers', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiGenerateDescriptionText(input: {
  channel_name: string
  genre: string
  match_key: string
  description: string
}): Promise<GenerateDescriptionTextResponse> {
  return platformRequest<GenerateDescriptionTextResponse>('/channel-setup/generate-description-text', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiGenerateKeywords(input: {
  channel_name: string
  genre: string
  match_key: string
  description: string
}): Promise<GenerateKeywordsResponse> {
  return platformRequest<GenerateKeywordsResponse>('/channel-setup/generate-keywords', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiGenerateTags(input: {
  channel_name: string
  genre: string
  match_key: string
  description: string
}): Promise<GenerateTagsResponse> {
  return platformRequest<GenerateTagsResponse>('/channel-setup/generate-tags', {
    method: 'POST',
    body: input,
    auth: true,
  })
}

export async function apiCreateProfile(input: {
  name: string
  genre: string
  role: 'primary' | 'secondary'
  logo_base64: string | null
  cover_images: string[]
  description: string
  keywords: string[]
  tags: string[]
  match_key: string
}): Promise<CreateProfileResponse> {
  return platformRequest<CreateProfileResponse>('/channel-setup/create-profile', {
    method: 'POST',
    body: input,
    auth: true,
  })
}
