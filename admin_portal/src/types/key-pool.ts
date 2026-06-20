export type KeyStatus = 'active' | 'rate_limited' | 'exhausted' | 'disabled';
export type SelectionStrategy = 'round_robin' | 'priority';
export type HealthIndicator = 'healthy' | 'degraded' | 'critical';

export interface ApiKeyEntry {
  id: string;
  provider: string;
  label: string;
  masked_key: string;
  priority: number;
  status: KeyStatus;
  total_requests: number;
  daily_requests: number;
  success_count: number;
  failure_count: number;
  rate_limit_hits: number;
  last_used_at: string | null;
  last_failure_at: string | null;
  cooldown_remaining_seconds: number | null;
  created_at: string;
}

export interface ProviderConfig {
  provider: string;
  selection_strategy: SelectionStrategy;
  cooldown_seconds: number;
}

export interface ProviderHealth {
  provider: string;
  total_keys: number;
  active_keys: number;
  rate_limited_keys: number;
  exhausted_keys: number;
  disabled_keys: number;
  health_indicator: HealthIndicator;
}

export interface KeyStatusEvent {
  id: string;
  key_label: string;
  previous_status: KeyStatus;
  new_status: KeyStatus;
  trigger_reason: string;
  http_status_code: number | null;
  created_at: string;
}

export interface AddKeyRequest {
  key_value: string;
  label: string;
  priority?: number;
}

export interface UpdateKeyRequest {
  label?: string;
  priority?: number;
  key_value?: string;
}

export interface ProviderConfigRequest {
  selection_strategy: SelectionStrategy;
  cooldown_seconds: number;
}

export interface AllProvidersHealth {
  providers: ProviderHealth[];
}
