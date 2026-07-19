export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UserListParams {
  page?: number;
  page_size?: number;
  status?: 'active' | 'suspended' | 'deleted';
  from_date?: string;
  to_date?: string;
}

export interface AuditLogParams {
  page?: number;
  page_size?: number;
  actor_id?: string;
  action_type?: string;
  resource_type?: string;
  outcome?: 'success' | 'failure';
  endpoint_path?: string;
  from_date?: string;
  to_date?: string;
}

export interface UsageListParams {
  page?: number;
  page_size?: number;
  user_id?: string;
  provider?: string;
  operation?: string;
  direction?: string;
  reason?: string;
  from_date?: string;
  to_date?: string;
}

export interface CreditAdjustmentRequest {
  user_id: string;
  amount: number;
  reason: string;
}

export interface CreateLicenseRequest {
  plan_id: string;
}

export interface AssignLicenseRequest {
  user_id: string;
}

export interface CreateOfferRequest {
  plan_id: string;
  promo_price_cents: number;
  max_redemptions: number;
}

export interface CreateRedeemCodeRequest {
  code: string;
  description?: string | null;
  reward_type: 'discount_amount' | 'discount_percentage' | 'credit_grant';
  discount_amount_cents?: number | null;
  discount_percent?: number | null;
  credit_amount?: number | null;
  applicable_plan_id?: string | null;
  max_redemptions?: number | null;
  per_user_limit: number;
  starts_at?: string | null;
  expires_at?: string | null;
  is_active: boolean;
}

export interface UpdateRedeemCodeRequest extends CreateRedeemCodeRequest {}

export interface RedeemRedemptionListParams {
  page?: number;
  page_size?: number;
  code?: string;
  reward_type?: 'discount_amount' | 'discount_percentage' | 'credit_grant';
  status?: string;
}

export interface UpdateSignupModeRequest {
  mode: 'open' | 'invite_only';
}

export interface CreateInvitationCodeRequest {
  label?: string | null;
  max_uses: number;
  expires_at?: string | null;
  is_active: boolean;
}

export interface UpdateInvitationCodeRequest {
  label?: string | null;
  max_uses?: number | null;
  expires_at?: string | null;
  is_active?: boolean | null;
}

export interface CreateCreditPackRequest {
  name: string;
  price_cents: number;
  song_credits: number;
  is_active?: boolean;
}

export interface UpdateCreditPackRequest extends CreateCreditPackRequest {
  id: string;
}

export interface CreatePricingRequest {
  ai_service: string;
  operation_type: string;
  sub_model?: string;
  lookup_sub_model?: string;
  credits_per_operation: number;
  external_cost_cents: number;
}

export interface CreateModelCostRequest {
  ai_service: string;
  operation_type: string;
  sub_model?: string;
  cost_usd: number;
  notes?: string;
}

export interface GeneratePricingRequest {
  margin_percent: number;
  overwrite_existing?: boolean;
  mark_needs_review?: boolean;
}

export interface SeedRegistryPricingRequest {
  margin_percent: number;
}

export interface RegistryPricingGapEntry {
  ai_service: string;
  operation_type: string;
  sub_model?: string;
}

export interface RegistryPricingGapsResponse {
  gap_count: number;
  gaps: RegistryPricingGapEntry[];
}

export interface UpdateGlobalCreditValueRequest {
  value: number;
}

export interface UpdateRateLimitRequest {
  endpoint_type: string;
  max_requests: number;
  window_seconds: number;
}

export interface UpdateSlaiImageProviderConfigRequest {
  min_interval_seconds: number;
  max_concurrent: number;
  provider_retries: number;
  retry_base_delay_seconds: number;
  retry_max_delay_seconds: number;
  fallback_provider_retries: number;
}

export interface CreatePromptRequest {
  name: string;
  content: string;
  match_key?: string;
  is_active?: boolean;
}
