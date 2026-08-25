import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import httpClient from '@/lib/http-client';
import type { AssignmentsResponse, ProvidersResponse, OperationAssignment, AIRoutingAuditResponse } from '@/types/ai-routing';

// --- Query Keys ---

const aiRoutingKeys = {
  all: ['ai-routing'] as const,
  assignments: () => ['ai-routing', 'assignments'] as const,
  providers: () => ['ai-routing', 'providers'] as const,
  audit: () => ['ai-routing', 'audit'] as const,
};

// --- Queries ---

export function useAIRoutingAssignments() {
  return useQuery({
    queryKey: aiRoutingKeys.assignments(),
    queryFn: () =>
      httpClient.get<AssignmentsResponse>('/api/v3/admin/ai-routing'),
  });
}

export function useAIRoutingProviders() {
  return useQuery({
    queryKey: aiRoutingKeys.providers(),
    queryFn: () =>
      httpClient.get<ProvidersResponse>('/api/v3/admin/ai-routing/providers'),
  });
}

export function useAIRoutingAudit() {
  return useQuery({
    queryKey: aiRoutingKeys.audit(),
    queryFn: () =>
      httpClient.get<AIRoutingAuditResponse>('/api/v3/admin/ai-routing/audit'),
  });
}

// --- Mutations ---

export function useSaveAIRoutingAssignments() {
  const queryClient = useQueryClient();
  return useMutation<
    { pricing_sync?: { created_count?: number } },
    Error,
    {
      assignments: Record<string, OperationAssignment>;
      text_fallback_chain?: OperationAssignment[];
      image_fallback_chain?: OperationAssignment[];
    }
  >({
    mutationFn: (payload: {
      assignments: Record<string, OperationAssignment>;
      text_fallback_chain?: OperationAssignment[];
      image_fallback_chain?: OperationAssignment[];
    }) =>
      httpClient.put<{ pricing_sync?: { created_count?: number } }>(
        '/api/v3/admin/ai-routing',
        payload,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: aiRoutingKeys.assignments() });
      queryClient.invalidateQueries({ queryKey: aiRoutingKeys.audit() });
    },
  });
}
