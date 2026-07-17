export interface OperationAssignment {
  provider: string;
  sub_model: string | null;
  is_active?: boolean;
}

export interface ProviderOption {
  provider: string;
  sub_models: string[];
  sub_models_detail?: SubModelDetail[];
}

export interface SubModelDetail {
  name: string;
  cost_tier: string; // "$" = cheapest, "$$" = moderate, "$$$" = premium
}

export interface AssignmentsResponse {
  text_generation: Record<string, OperationAssignment>;
  image_generation: Record<string, OperationAssignment>;
  music_generation: Record<string, OperationAssignment>;
  text_fallback_chain: OperationAssignment[];
  image_fallback_chain: OperationAssignment[];
}

export interface ProvidersResponse {
  text_generation: ProviderOption[];
  image_generation: ProviderOption[];
  music_generation: ProviderOption[];
}

export interface CapabilityIssue {
  severity: 'error' | 'warning';
  code: string;
  message: string;
  operation?: string | null;
  provider?: string | null;
  sub_model?: string | null;
  pricing_ai_service?: string | null;
  pricing_operation_type?: string | null;
}

export interface AIRoutingAuditResponse {
  catalog: {
    providers: Array<{
      provider: string;
      service_types: string[];
      text_llm: boolean;
      text_models: string[];
      image_models: string[];
      music_models: string[];
    }>;
    operations: Array<{
      operation: string;
      service_type: string;
      pricing_operation_type: string;
    }>;
    text_llm_providers: string[];
  };
  issues: CapabilityIssue[];
  error_count: number;
  warning_count: number;
  draft_pricing_count?: number;
  ready: boolean;
}
