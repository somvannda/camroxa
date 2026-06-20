import { useEffect } from 'react';
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
import { useUpdateKey } from '@/hooks/use-key-pool';
import type { ApiKeyEntry } from '@/types/key-pool';

const editKeySchema = z.object({
  label: z
    .string()
    .min(1, 'Label is required')
    .max(100, 'Label must be 100 characters or fewer'),
  priority: z.coerce
    .number()
    .int('Priority must be a whole number')
    .min(1, 'Priority must be at least 1')
    .max(100, 'Priority must be at most 100'),
  key_value: z
    .string()
    .max(500, 'Key value must be 500 characters or fewer')
    .optional()
    .or(z.literal('')),
});

type EditKeyFormValues = z.infer<typeof editKeySchema>;

interface EditKeyDialogProps {
  provider: string;
  entry: ApiKeyEntry | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditKeyDialog({
  provider,
  entry,
  open,
  onOpenChange,
}: EditKeyDialogProps) {
  const updateKey = useUpdateKey(provider);

  const form = useForm<EditKeyFormValues>({
    resolver: zodResolver(editKeySchema),
    defaultValues: {
      label: entry?.label ?? '',
      priority: entry?.priority ?? 50,
      key_value: '',
    },
  });

  useEffect(() => {
    if (entry && open) {
      form.reset({
        label: entry.label,
        priority: entry.priority,
        key_value: '',
      });
    }
  }, [entry, open, form]);

  function onSubmit(values: EditKeyFormValues) {
    if (!entry) return;

    const updates: Record<string, string | number> = {};
    if (values.label !== entry.label) updates.label = values.label;
    if (values.priority !== entry.priority) updates.priority = values.priority;
    if (values.key_value && values.key_value.length > 0) {
      updates.key_value = values.key_value;
    }

    if (Object.keys(updates).length === 0) {
      onOpenChange(false);
      return;
    }

    updateKey.mutate(
      { keyId: entry.id, updates },
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
      updateKey.reset();
    }
    onOpenChange(nextOpen);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit API Key</DialogTitle>
          <DialogDescription>
            Update the label, priority, or key value for &ldquo;{entry?.label}&rdquo;.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="label"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Label</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. Production Key 1" {...field} />
                  </FormControl>
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
                    <Input type="number" min={1} max={100} {...field} />
                  </FormControl>
                  <FormDescription>
                    1 = highest priority, 100 = lowest.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="key_value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New Key Value (optional)</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder="Leave blank to keep current key"
                      autoComplete="off"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    Only fill this if you want to replace the existing key value.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {updateKey.isError && (
              <p className="text-sm text-destructive">
                {updateKey.error?.message ?? 'Failed to update key. Please try again.'}
              </p>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={updateKey.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateKey.isPending}>
                {updateKey.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Save Changes
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
