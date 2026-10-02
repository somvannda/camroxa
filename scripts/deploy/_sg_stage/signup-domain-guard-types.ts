export interface SignupDomainGuardConfig {
  blocked: string[];
  trusted: string[];
  max_free: number;
}

export interface SignupDomainAccount {
  id: string;
  email: string;
  status: string;
  email_confirmed: boolean;
  products: string[];
  created_at: string | null;
}

export interface SignupDomainAccountsResponse {
  domain: string;
  accounts: SignupDomainAccount[];
  count: number;
}

export interface SignupDomainGuardPayload {
  blocked?: string[];
  trusted?: string[];
  max_free?: number;
}

export type SignupDomainAction =
  | 'block'
  | 'unblock'
  | 'freeze'
  | 'unfreeze'
  | 'suspend'
  | 'reactivate';

export interface SignupDomainActionRequest {
  domain: string;
  action: SignupDomainAction;
  hours?: number;
  reason?: string;
}

export interface SignupDomainActionResponse {
  ok: boolean;
  action: SignupDomainAction;
  domain: string;
  affected_accounts: number;
  blocked_count?: number;
  hours?: number;
}
