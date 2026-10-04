import { Loader2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from '@/components/ui/form';
import { useAddKey } from '@/hooks/use-key-pool';
import { UPSTREAM_HOST_PRESETS } from '@/types/key-pool';

const addKeySchema = z.object({
  key_value: z
    .string()
    .min(1, 'Key value is required')
    .max(500, 'Key value must be 500 characters or fewer'),
  label: z
    .string()
    .min(1, 'Label is required')
    .max(100, 'Label must be 100 characters or fewer'),
  priority: z.coerce
    .number()
    .int('Priority must be a whole number')
    .min(1, 'Priority must be at least 1')
    .max(100, 'Priority must be at most 100'),
  base_url: z
    .string()
    .max(500, 'Host must be 500 characters or fewer')
    .optional()
    .or(z.literal('')),
});

type AddKeyFormValues = z.infer<typeof addKeySchema>;

interface AddKeyDialogProps {
  provider: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddKeyDialog({ provider, open, onOpenChange }: AddKeyDialogProps) {
  const addKey = useAddKey(provider);

  const form = useForm<AddKeyFormValues>({
    resolver: zodResolver(addKeySchema),
    defaultValues: {
      key_value: '',
      label: '',
      priority: 50,
      base_url: '',
    },
  });

  function onSubmit(values: AddKeyFormValues) {
    addKey.mutate(
      {
        ...values,
        base_url: values.base_url?.trim() ? values.base_url.trim() : null,
      },
      {
        onSuccess: () => {
          form.reset();
          onOpenChange(false);
        },
      },
    );
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      form.reset();
      addKey.reset();
    }
    onOpenChange(nextOpen);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add API Key</DialogTitle>
          <DialogDescription>
            Add a new API key to the {provider} pool.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="key_value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>API Key Value</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder="sk-..."
                      autoComplete="off"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    The key will be encrypted at rest.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="label"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Label</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="e.g. Production Key 1"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    A unique label to identify this key within the provider.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="priority"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Priority</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      min={1}
                      max={100}
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    1 = highest priority, 100 = lowest. Default is 50.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="base_url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Upstream Host (optional)</FormLabel>
                  <FormControl>
                    <Input
                      list="add-key-host-presets"
                      placeholder="Leave blank for host-agnostic"
                      {...field}
                    />
                  </FormControl>
                  <datalist id="add-key-host-presets">
                    {UPSTREAM_HOST_PRESETS.map((preset) => (
                      <option key={preset.value} value={preset.value}>
                        {preset.label}
                      </option>
                    ))}
                  </datalist>
                  <FormDescription>
                    Tag the key with its host so the provider can switch between
                    upstreams.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {addKey.isError && (
              <p className="text-sm text-destructive">
                {addKey.error?.message ?? 'Failed to add key. Please try again.'}
              </p>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={addKey.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={addKey.isPending}>
                {addKey.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add Key
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
