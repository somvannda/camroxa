import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { AxiosError } from 'axios';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { ErrorState } from '@/components/shared/error-state';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Skeleton } from '@/components/ui/skeleton';
import { useRateLimits, useUpdateRateLimit } from '@/hooks/use-rate-limits';
import { toast } from '@/hooks/use-toast';
import type { RateLimitConfig } from '@/types/models';

// --- Zod Schema ---

const rateLimitSchema = z.object({
  endpoint_type: z.string(),
  max_requests: z
    .number({ invalid_type_error: 'Must be a number' })
    .min(1, 'Must be at least 1')
    .max(100000, 'Must be at most 100,000'),
  window_seconds: z
    .number({ invalid_type_error: 'Must be a number' })
    .min(1, 'Must be at least 1 second')
    .max(86400, 'Must be at most 86,400 seconds (24 hours)'),
});

type RateLimitFormValues = z.infer<typeof rateLimitSchema>;

// --- Component ---

export default function RateLimitsPage() {
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedConfig, setSelectedConfig] = useState<RateLimitConfig | null>(null);

  const {
    data: rateLimits,
    isLoading,
    isError,
    error,
    refetch,
  } = useRateLimits();
  const updateRateLimit = useUpdateRateLimit();

  const form = useForm<RateLimitFormValues>({
    resolver: zodResolver(rateLimitSchema),
    defaultValues: {
      endpoint_type: '',
      max_requests: 100,
      window_seconds: 60,
    },
  });

  const openEditDialog = (config: RateLimitConfig) => {
    setSelectedConfig(config);
    form.reset({
      endpoint_type: config.endpoint_type,
      max_requests: config.max_requests,
      window_seconds: config.window_seconds,
    });
    setEditDialogOpen(true);
  };

  const handleUpdate = (values: RateLimitFormValues) => {
    updateRateLimit.mutate(values, {
      onSuccess: () => {
        toast({
          title: 'Rate limit updated',
          description: 'Changes take effect within 5 seconds.',
        });
        setEditDialogOpen(false);
        setSelectedConfig(null);
      },
      onError: (err) => {
        const axiosError = err as AxiosError<{ detail?: string }>;
        toast({
          title: 'Error',
          description:
            axiosError.response?.data?.detail ?? 'Failed to update rate limit',
          variant: 'destructive',
        });
      },
    });
  };

  if (isError && !rateLimits) {
    return (
      <div className="p-6">
        <h1 className="mb-6 text-2xl font-bold text-slate-100">Rate Limits</h1>
        <ErrorState
          message={error?.message ?? 'Failed to load rate limits'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Rate Limits</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Endpoint Rate Limit Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-slate-400">
                    <th className="pb-3 pr-4 font-medium">Endpoint Type</th>
                    <th className="pb-3 pr-4 font-medium">Max Requests</th>
                    <th className="pb-3 pr-4 font-medium">Window</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rateLimits?.map((config) => (
                    <tr
                      key={config.id}
                      className="border-b border-slate-800 hover:bg-slate-800/50"
                    >
                      <td className="py-3 pr-4 text-slate-200 font-medium">
                        {config.endpoint_type}
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        {config.max_requests.toLocaleString()}
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        {config.window_seconds} seconds
                      </td>
                      <td className="py-3">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openEditDialog(config)}
                        >
                          Edit
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rateLimits?.length === 0 && (
                <p className="py-8 text-center text-slate-400">
                  No rate limit configurations found.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Rate Limit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Rate Limit</DialogTitle>
            <DialogDescription>
              Update rate limit for &quot;{selectedConfig?.endpoint_type}&quot;
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleUpdate)} className="space-y-4">
              <FormField
                control={form.control}
                name="endpoint_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Endpoint Type</FormLabel>
                    <FormControl>
                      <Input {...field} disabled className="bg-slate-800/50" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="max_requests"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Max Requests (1 – 100,000)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        {...field}
                        onChange={(e) => field.onChange(Number(e.target.value))}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="window_seconds"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Window (1 – 86,400 seconds)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        {...field}
                        onChange={(e) => field.onChange(Number(e.target.value))}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setEditDialogOpen(false)}
                  disabled={updateRateLimit.isPending}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={updateRateLimit.isPending}>
                  {updateRateLimit.isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Save Changes
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
