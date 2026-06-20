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

export interface CreatePricingRequest {
  model_identifier: string;
  operation_type: string;
  credits_per_operation: number;
  external_cost_cents: number;
}

export interface UpdateRateLimitRequest {
  endpoint_type: string;
  max_requests: number;
  window_seconds: number;
}

export interface CreatePromptRequest {
  name: string;
  content: string;
  match_key?: string;
}
