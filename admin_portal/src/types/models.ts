export interface User {
  id: string;
  email: string;
  display_name: string;
  role: 'user' | 'admin';
  status: 'active' | 'suspended' | 'deleted';
  suspension_reason?: string;
  credit_balance: number;
  plan_name: string | null;
  music_credits_remaining?: number | null;
  music_credits_limit?: number | null;
  credits_burned?: number | null;
  channel_profile_count: number;
  products?: string[];
  email_confirmed?: boolean;
  pending_verification_code?: string | null;
  verification_code_expires_at?: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface UserFullDetail {
  id: string;
  email: string;
  display_name: string;
  role: 'user' | 'admin';
  status: 'active' | 'suspended' | 'deleted';
  suspension_reason?: string;
  created_at: string;
  updated_at: string | null;

  // Credits
  credit_balance: number;
  total_credits_spent: number;
  music_credits_remaining?: number | null;
  music_credits_limit?: number | null;
  credits_burned?: number | null;
  recent_transactions: {
    id: string;
    amount: number;
    amount_units?: number;
    direction: string;
    reason: string;
    purpose?: string;
    provider?: string | null;
    model?: string | null;
    operation?: string | null;
    line_items_summary?: string | null;
    ref_id?: string | null;
    batch_id?: string | null;
    song_id?: string | null;
    attempts_used?: number | null;
    created_at: string | null;
  }[];

  // Plan/License
  plan_name: string | null;
  plan_id: string | null;
  license_status: string | null;
  license_activated_at: string | null;
  license_expires_at: string | null;

  // Profiles
  channel_profiles: {
    id: string;
    name: string;
    folder_name: string | null;
    run_prefix: string | null;
    created_at: string | null;
    logo_available: boolean;
    cover_count: number;
    output_resolution: string | null;
    video_template_id: string | null;
    reel_template_id: string | null;
    video_template_name: string | null;
    video_template_updated_at: string | null;
    video_template_available: boolean;
    reel_template_name: string | null;
    reel_template_updated_at: string | null;
    reel_template_available: boolean;
    genre: string | null;
    role: string | null;
    description: string | null;
    visibility: string | null;
    publish_at: string | null;
    made_for_kids: boolean;
    ai_use: boolean;
    category: string | null;
    playlist: string | null;
    title_template: string | null;
    description_template: string | null;
    keywords: string[];
    tags: string[];
  }[];

  // Usage stats
  total_songs_generated: number;
  total_images_generated: number;

  /** Current billing-period quotas including admin top-ups. */
  quota_period?: QuotaPeriodSnapshot | null;

  custom_descriptions: UserOwnedPromptSummary[];
  custom_structures: UserOwnedPromptSummary[];

  generation_frozen?: boolean;
  generation_frozen_reason?: string | null;
  generation_frozen_hours?: number | null;
  generation_frozen_retry_after?: number;
}

export interface QuotaKindStatus {
  quota_kind: string;
  base_limit: number | null;
  topup_extra: number;
  effective_limit: number | null;
  used: number;
  remaining: number | null;
}

export interface QuotaPeriodSnapshot {
  period_start: string | null;
  period_end: string | null;
  plan_name: string | null;
  kinds: Record<string, QuotaKindStatus>;
}

export interface UserOwnedPromptSummary {
  id: string;
  name: string;
  content: string;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface AdminUserOwnedPrompt {
  id: string;
  user_id: string;
  user_email: string;
  user_display_name: string;
  name: string;
  content: string;
  is_active: boolean;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface License {
  id: string;
  license_key: string;
  plan_id: string;
  user_id: string | null;
  status: 'unassigned' | 'active' | 'expired' | 'revoked' | 'cancelled' | 'pending';
  profile_addon_slots: number;
  profile_addon_pending: number;
  activated_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
  source?: 'desktop' | 'web';
  user_email?: string | null;
  plan_name?: string | null;
}

export interface Plan {
  id: string;
  name: string;
  price_cents: number;
  billing_cycle_days: number | null;
  profile_allowance: number;
  monthly_song_limit: number | null;
  monthly_image_limit: number | null;
  monthly_draft_limit: number | null;
  monthly_video_limit: number | null;
  monthly_merge_limit: number | null;
  daily_song_limit_per_channel: number;
  daily_image_limit_per_channel: number;
  daily_draft_limit_per_channel: number;
  daily_video_limit: number;
  daily_merge_limit: number;
  is_active: boolean;
  effective_from: string;
  created_at: string;
  updated_at: string;
  subscriber_count: number;
  can_delete: boolean;
  plan_kind?: 'subscription' | 'profile_addon';
  plan_type?: 'desktop_pro' | 'web_music';
}

export interface WebMusicPlan {
  id: string;
  name: string;
  price_cents: number;
  billing_cycle_days: number;
  monthly_credits: number;
  features: {
    music: boolean;
    images: boolean;
    topup: boolean;
  };
  is_public: boolean;
  display_order: number;
  is_active: boolean;
  subscriber_count: number;
  can_delete: boolean;
  created_at: string;
  updated_at: string;
}

export interface WebMusicTopupPack {
  id: string;
  slug: string;
  name: string;
  total_credits: number;
  price_cents: number;
  display_order: number;
  is_active: boolean;
  songs_equivalent: number;
  created_at: string;
  updated_at: string;
}

export interface PlanOffer {
  id: string;
  plan_id: string;
  promo_price_cents: number;
  max_redemptions: number;
  current_redemptions: number;
  is_active: boolean;
  created_at: string;
}

export interface RedeemCode {
  id: string;
  code: string;
  description: string | null;
  reward_type: 'discount_amount' | 'discount_percentage' | 'credit_grant';
  discount_amount_cents: number | null;
  discount_percent: number | null;
  credit_amount: number | null;
  applicable_plan_id: string | null;
  applicable_plan_name: string | null;
  max_redemptions: number | null;
  current_redemptions: number;
  remaining_redemptions: number | null;
  per_user_limit: number;
  starts_at: string | null;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RedeemCodeRedemption {
  id: string;
  redeem_code_id: string;
  code: string;
  description: string | null;
  reward_type: 'discount_amount' | 'discount_percentage' | 'credit_grant';
  user_id: string;
  user_email: string | null;
  user_display_name: string | null;
  billing_payment_id: string | null;
  plan_id: string | null;
  plan_name: string | null;
  status: string;
  amount_cents: number | null;
  credit_amount: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface RedeemCodeRedemptionListResponse {
  items: RedeemCodeRedemption[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SignupModeResponse {
  mode: 'open' | 'invite_only';
}

export interface InvitationCodeAdminItem {
  id: string;
  code: string | null;
  code_hint: string;
  label: string | null;
  max_uses: number;
  current_uses: number;
  remaining_uses: number | null;
  is_active: boolean;
  expires_at: string | null;
  created_at: string;
}

export interface InvitationCodeCreateResponse extends Omit<InvitationCodeAdminItem, 'code'> {
  code: string;
}

export interface CreditPricing {
  id: string;
  model_identifier: string;
  ai_service: string;
  operation_type: string;
  sub_model?: string;
  credits_per_operation: number;
  external_cost_cents: number | null;
  sell_price_cents: number | null;
  profit_margin_cents: number | null;
  profit_margin_percent: number | null;
  needs_review?: boolean;
  created_at: string;
  updated_at: string;
}

export interface ModelCost {
  id: string;
  ai_service: string;
  sub_model: string;
  operation_type: string;
  cost_usd: number;
  notes: string | null;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface ServiceAvailabilityEntry {
  ai_service: string;
  status: 'available' | 'degraded' | 'unavailable';
}

export interface GlobalCreditValueResponse {
  global_credit_value: number | null;
}

export interface CreditPack {
  id: string;
  name: string;
  price_cents: number;
  song_credits: number;
  request_count: number;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface MusicDescription {
  id: string;
  name: string;
  content: string;
  genres?: string[];
  match_key: string | null;
  vocal_profile?: VocalProfile | null;
  is_active: boolean;
  owner_label?: string;
  usage_count?: number;
  created_at: string;
  updated_at: string;
}

export interface VocalProfile {
  mode: 'monolingual' | 'bilingual';
  primary_language?: string;
  secondary_language?: string;
  verse_role?: 'primary' | 'secondary';
  chorus_role?: 'primary' | 'secondary';
  section_language_map?: Record<string, 'primary' | 'secondary'>;
}

export interface MusicStructure {
  id: string;
  name: string;
  content: string;
  match_key: string | null;
  is_active: boolean;
  owner_label?: string;
  usage_count?: number;
  created_at: string;
  updated_at: string;
}

export interface MusicMood {
  id: string;
  name: string;
  content: string;
  match_key: string | null;
  is_active: boolean;
  user_id?: string | null;
  owner_label?: string;
  usage_count?: number;
  created_at: string;
  updated_at: string;
}

export interface PromptUsageByUser {
  user_id: string;
  user_email: string;
  user_display_name: string;
  usage_count: number;
  last_used_at: string | null;
}

export interface PromptUsageByProfile {
  profile_id: string;
  profile_name: string;
  user_email: string;
  user_display_name: string;
  usage_count: number;
  last_used_at: string | null;
}

export interface PromptUsageByDay {
  usage_date: string;
  usage_count: number;
}

export interface PromptUsageResponse {
  prompt_id: string;
  prompt_name: string;
  owner_label: string;
  usage_count: number;
  users: PromptUsageByUser[];
  profiles: PromptUsageByProfile[];
  by_day: PromptUsageByDay[];
}

export interface ChannelPrompt {
  id: string;
  name: string;
  content: string;
  category: string;
  genre: string;
  match_key: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RateLimitConfig {
  id: string;
  endpoint_type: string;
  max_requests: number;
  window_seconds: number;
  updated_at: string;
}

export interface SlaiImageProviderConfig {
  min_interval_seconds: number;
  max_concurrent: number;
  provider_retries: number;
  retry_base_delay_seconds: number;
  retry_max_delay_seconds: number;
  fallback_provider_retries: number;
}

export interface AuditEntry {
  id: string;
  actor_id: string | null;
  actor_email?: string | null;
  actor_display_name?: string | null;
  actor_role?: string | null;
  actor_label?: string | null;
  action_type: string;
  target_resource: string | null;
  outcome: 'success' | 'failure';
  credit_impact: number;
  credits_involved: boolean;
  credit_summary: string;
  credit_direction?: string | null;
  credit_reason?: string | null;
  credit_reference?: string | null;
  payment_reference?: string | null;
  source_ip: string | null;
  client_id?: string | null;
  endpoint_path: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface ClientLogBatchSummary {
  id: string;
  user_id: string;
  client_id: string | null;
  client_label: string | null;
  app_version: string | null;
  line_count: number;
  size_bytes: number;
  created_at: string;
  preview: string | null;
}

export interface ClientLogDetail extends ClientLogBatchSummary {
  content: string;
}

export interface UsageLineItem {
  operation: string;
  provider?: string | null;
  model?: string | null;
  amount_units?: number | null;
  amount?: number | null;
}

export interface UsageEntry {
  id: string;
  user_id: string;
  user_email: string;
  user_display_name: string;
  amount: number;
  amount_units: number;
  direction: string;
  reason: string;
  purpose: string;
  provider?: string | null;
  model?: string | null;
  operation?: string | null;
  category?: string | null;
  line_items_summary?: string | null;
  line_items: UsageLineItem[];
  ref_id?: string | null;
  batch_id?: string | null;
  song_id?: string | null;
  batch_index?: number | null;
  attempts_used?: number | null;
  llm_calls_title?: number | null;
  llm_calls_album?: number | null;
  llm_calls_lyric?: number | null;
  source?: string | null;
  billing?: string | null;
  list_credit_units?: number | null;
  charged_credit_units?: number | null;
  coverage?: string | null;
  metadata?: Record<string, unknown> | null;
  legacy?: boolean;
  created_at?: string | null;
}

export interface UsageFiltersResponse {
  providers: string[];
  operations: string[];
}

export interface UsageOperationSummary {
  operation: string;
  /** Provider from tx metadata / reason (may be empty). */
  provider?: string;
  /** Model / sub_model from tx metadata (may be empty). */
  model?: string;
  events: number;
  wallet_charged: number;
  plan_included_list: number;
}

export interface UsageSummary {
  billable_events: number;
  credit_cost: number;
  refund_total: number;
  refund_events: number;
  net_credit_cost: number;
  wallet_charged: number;
  plan_included_list: number;
  plan_allowance_events: number;
  plan_draft_list?: number;
  plan_song_list?: number;
  plan_image_list?: number;
  platform_absorb_events?: number;
  platform_absorb_list?: number;
  subscription_revenue_cents?: number;
  subscription_payment_count?: number;
  credit_pack_revenue_cents?: number;
  credit_pack_payment_count?: number;
  grant_issued?: number;
  grant_issued_events?: number;
  by_operation: UsageOperationSummary[];
}

export interface UsageListResponse {
  items: UsageEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  summary: UsageSummary;
}

export interface UserSpendMeter {
  used: number;
  limit: number | null;
  pct: number | null;
  hot: boolean;
}

export interface UserSpendCog {
  provider: string;
  operation: string;
  model: string;
  events: number;
  plan_included_usd: number;
  wallet_usd: number;
  est_cogs_usd: number | null;
  coverage: string;
}

export interface UserSpendAlerts {
  over_allowance: boolean;
  margin_risk: boolean;
  meters_hot: string[];
}

export interface UserSpendItem {
  user_id: string;
  email: string;
  display_name: string | null;
  plan_id: string | null;
  plan_name: string;
  plan_price_cents: number;
  billing_cycle_days: number | null;
  plan_revenue_usd: number;
  est_cogs_usd: number;
  wallet_charged_usd: number;
  plan_included_usd: number;
  soft_overage_events: number;
  meters: Record<string, UserSpendMeter>;
  alerts: UserSpendAlerts;
  by_cog: UserSpendCog[];
}

export interface UserSpendSummary {
  users_over_allowance: number;
  users_margin_risk: number;
  total_est_cogs_usd: number;
  total_wallet_usd: number;
  gcv: number;
}

export interface UserSpendListResponse {
  items: UserSpendItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  summary: UserSpendSummary;
}

export interface AdminBatchSongSummary {
  id: string;
  batch_index: number;
  title?: string | null;
  album?: string | null;
  status: string;
}

export interface AdminBatchSummary {
  id: string;
  user_id: string;
  user_email: string;
  user_display_name: string;
  status: string;
  song_count: number;
  language: string;
  created_at?: string | null;
  updated_at?: string | null;
  songs: AdminBatchSongSummary[];
}

export interface AdminSongSummary {
  id: string;
  batch_id: string;
  batch_index: number;
  user_id: string;
  user_email: string;
  user_display_name: string;
  title?: string | null;
  album?: string | null;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  /** Raw PLATFORM_ENVIRONMENT value (e.g. staging, production). */
  environment?: string;
  /** Ops-facing label (Sandbox / Production / …). */
  environment_label?: string;
  database?: boolean;
  services: Record<string, ServiceHealth | boolean>;
  uptime_seconds?: number;
  timestamp?: string;
}

export interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  latency_ms?: number;
  message?: string;
}
