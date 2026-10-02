export type SunoBlocklistSeverity = 'block' | 'warn';
export type SunoBlocklistSource = 'manual' | 'learned';

export interface SunoBlocklistTerm {
  id: string;
  term: string;
  replacement: string | null;
  severity: SunoBlocklistSeverity;
  source: SunoBlocklistSource;
  enabled: boolean;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SunoBlocklistListResponse {
  items: SunoBlocklistTerm[];
}

export interface CreateSunoBlocklistRequest {
  term: string;
  replacement?: string | null;
  severity?: SunoBlocklistSeverity;
  enabled?: boolean;
  notes?: string | null;
}

export interface UpdateSunoBlocklistRequest {
  term?: string;
  replacement?: string | null;
  severity?: SunoBlocklistSeverity;
  enabled?: boolean;
  notes?: string | null;
  clear_replacement?: boolean;
}

export interface SunoFailureMetricBucket {
  failure_type: string;
  submit_kind: 'first_submit' | 'retry';
  count: number;
}

export interface SunoFailureMetricsResponse {
  days: number;
  total: number;
  buckets: SunoFailureMetricBucket[];
}

export interface PromoteSunoBlocklistRequest {
  term: string;
  replacement?: string | null;
  severity?: SunoBlocklistSeverity;
  notes?: string | null;
}
