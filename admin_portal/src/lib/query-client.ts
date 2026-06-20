import { MutationCache, QueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { toast } from '@/hooks/use-toast';

/**
 * Extract a user-friendly error message from an error object.
 * Handles AxiosError responses with detail/message fields,
 * generic Error instances, and unknown errors.
 */
function extractErrorMessage(error: unknown): string {
  if (error instanceof AxiosError && error.response?.data) {
    const data = error.response.data as Record<string, unknown>;
    if (typeof data.detail === 'string') return data.detail;
    if (typeof data.message === 'string') return data.message;
  }
  if (error instanceof Error) return error.message;
  return 'An unexpected error occurred';
}

/**
 * Global mutation cache with error handling.
 * Shows a destructive toast notification for any mutation error.
 */
const mutationCache = new MutationCache({
  onError: (error) => {
    toast({
      variant: 'destructive',
      title: 'Error',
      description: extractErrorMessage(error),
    });
  },
});

/**
 * TanStack Query client configured for the Admin Portal.
 *
 * - Queries: staleTime of 30s, retry up to 3 times for network/5xx errors,
 *   no retry for 4xx client errors.
 * - Mutations: no automatic retry; global error handling via MutationCache
 *   displays toast notifications.
 */
export const queryClient = new QueryClient({
  mutationCache,
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30 seconds
      retry: (failureCount, error) => {
        // Don't retry on 4xx client errors
        if (error instanceof AxiosError && error.response) {
          const status = error.response.status;
          if (status >= 400 && status < 500) return false;
        }
        // Retry up to 3 times for network/5xx errors
        return failureCount < 3;
      },
    },
    mutations: {
      retry: false,
    },
  },
});
