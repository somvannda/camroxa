export interface User {
  id: string;
  email: string;
  display_name: string;
  role: 'user' | 'admin';
  status: 'active' | 'suspended' | 'deleted';
  suspension_reason?: string;
  created_at: string;
  updated_at: string;
}

export interface License {
  id: string;
  license_key: string;
  plan_id: string;
  user_id: string | null;
  status: 'unassigned' | 'active' | 'expired' | 'revoked';
  activated_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface Plan {
  id: string;
  name: string;
  price_cents: number;
  billing_cycle_days: number | null;
  profile_allowance: number;
  monthly_song_quota: number | null;
  daily_song_limit_per_channel: number;
  is_active: boolean;
  effective_from: string;
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

export interface CreditPricing {
  id: string;
  model_identifier: string;
  operation_type: string;
  credits_per_operation: number;
  external_cost_cents: number | null;
  created_at: string;
  updated_at: string;
}

export interface CreditPack {
  id: string;
  name: string;
  price_cents: number;
  song_credits: number;
  request_count: number;
  is_active: boolean;
}

export interface MusicDescription {
  id: string;
  name: string;
  content: string;
  match_key: string | null;
  created_at: string;
  updated_at: string;
}

export interface MusicStructure {
  id: string;
  name: string;
  content: string;
  match_key: string | null;
  created_at: string;
  updated_at: string;
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

export interface AuditEntry {
  id: string;
  actor_id: string | null;
  action_type: string;
  target_resource: string | null;
  outcome: 'success' | 'failure';
  credit_impact: number;
  source_ip: string | null;
  endpoint_path: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  services: Record<string, ServiceHealth>;
}

export interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  latency_ms?: number;
  message?: string;
}
