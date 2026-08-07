export interface ProviderKeyBalanceItem {
  key_id: string;
  label: string;
  key_status: string;
  priority: number;
  balance: number | null;
  currency: string | null;
  unit: string;
  display: string | null;
  fetch_status: string;
  error: string | null;
  checked_at: string | null;
  /** Credits/money dropped since UTC day-start baseline (balance drop). */
  used_today?: number | null;
  day_start_balance?: number | null;
}

export interface ProviderKeyBalanceGroup {
  provider: string;
  keys: ProviderKeyBalanceItem[];
  error?: string | null;
}

export interface ProviderKeyBalancesResponse {
  providers: ProviderKeyBalanceGroup[];
  checked_at: string;
}
