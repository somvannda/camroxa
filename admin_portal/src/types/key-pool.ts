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
  /** Upstream host this key belongs to; null = host-agnostic (legacy). */
  base_url: string | null;
}

export interface ProviderConfig {
  provider: string;
  selection_strategy: SelectionStrategy;
  cooldown_seconds: number;
  /** Active upstream host; null = use the environment default and every key. */
  base_url: string | null;
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
  base_url?: string | null;
}

export interface UpdateKeyRequest {
  label?: string;
  priority?: number;
  key_value?: string;
  base_url?: string | null;
  clear_base_url?: boolean;
}

export interface ProviderConfigRequest {
  selection_strategy: SelectionStrategy;
  cooldown_seconds: number;
  base_url?: string | null;
  clear_base_url?: boolean;
}

/** Known Suno-compatible upstream hosts offered as presets in the admin UI. */
export const UPSTREAM_HOST_PRESETS: { label: string; value: string }[] = [
  { label: 'Camxora musicapi', value: 'https://musicapi.camxora.com' },
  { label: 'sunoapi.org (apibox)', value: 'https://apibox.erweima.ai' },
];

export interface AllProvidersHealth {
  providers: ProviderHealth[];
}
