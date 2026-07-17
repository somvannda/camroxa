import { useQuery } from '@tanstack/react-query'

import { apiGetBatchStatus } from '@/shared/api/platformEndpoints'

export function useBatchStatusQuery(batchId: string | null) {
  return useQuery({
    queryKey: ['music-batch-status', batchId],
    queryFn: () => apiGetBatchStatus(batchId as string),
    enabled: Boolean(batchId),
    refetchInterval: batchId ? 2500 : false,
  })
}

