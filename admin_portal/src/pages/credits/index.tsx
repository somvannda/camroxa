import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AxiosError } from 'axios';
import { Loader2, Plus, Pencil } from 'lucide-react';

import {
  usePricing,
  useCreatePricing,
  useUpdatePricing,
  usePacks,
  useAdjustBalance,
} from '@/hooks/use-credits';
import type { CreditPricing } from '@/types/models';
import { toast } from '@/hooks/use-toast';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';

// --- Validation Schemas ---

const pricingFormSchema = z.object({
  model_identifier: z.string().min(1, 'Model identifier is required'),
  operation_type: z.string().min(1, 'Operation type is required'),
  credits_per_operation: z.number({ coerce: true }).min(1, 'Must be at least 1'),
  external_cost_cents: z.number({ coerce: true }).min(0, 'Must be non-negative'),
});

type PricingFormValues = z.infer<typeof pricingFormSchema>;

const creditAdjustSchema = z.object({
  user_id: z.string().uuid('Valid user ID is required'),
  amount: z.number({ coerce: true }).refine((v) => v !== 0, 'Amount must be non-zero'),
  reason: z
    .string()
    .min(1, 'Reason is required')
    .transform((v) => v.trim()),
});

type CreditAdjustFormValues = z.infer<typeof creditAdjustSchema>;

// --- Helper ---

function formatCents(cents: number | null): string {
  if (cents === null) return '—';
  return `$${(cents / 100).toFixed(2)}`;
}

// --- Components ---

function PricingSection() {
  const { data: pricing, isLoading, isError, refetch } = usePricing();
  const createPricing = useCreatePricing();
  const updatePricing = useUpdatePricing();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<CreditPricing | null>(null);

  const form = useForm<PricingFormValues>({
    resolver: zodResolver(pricingFormSchema),
    defaultValues: {
      model_identifier: '',
      operation_type: '',
      credits_per_operation: 1,
      external_cost_cents: 0,
    },
  });

  function openCreateDialog() {
    setEditingItem(null);
    form.reset({
      model_identifier: '',
      operation_type: '',
      credits_per_operation: 1,
      external_cost_cents: 0,
    });
    setDialogOpen(true);
  }

  function openEditDialog(item: CreditPricing) {
    setEditingItem(item);
    form.reset({
      model_identifier: item.model_identifier,
      operation_type: item.operation_type,
      credits_per_operation: item.credits_per_operation,
      external_cost_cents: item.external_cost_cents ?? 0,
    });
    setDialogOpen(true);
  }

  async function onSubmit(values: PricingFormValues) {
    try {
      if (editingItem) {
        await updatePricing.mutateAsync({ id: editingItem.id, updates: values });
        toast({ title: 'Pricing updated successfully' });
      } else {
        await createPricing.mutateAsync(values);
        toast({ title: 'Pricing created successfully' });
      }
      setDialogOpen(false);
    } catch (error) {
      if (
        error instanceof AxiosError &&
        error.response?.status === 409
      ) {
        toast({
          variant: 'destructive',
          title: 'Conflict',
          description:
            'A pricing entry for this model/operation combination already exists',
        });
      }
      // Other errors handled by global mutation cache
    }
  }

  const isPending = createPricing.isPending || updatePricing.isPending;

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Pricing</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Pricing</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">Failed to load pricing data.</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Pricing</CardTitle>
        <Button size="sm" onClick={openCreateDialog}>
          <Plus className="mr-1 h-4 w-4" />
          Add Pricing
        </Button>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead>Operation Type</TableHead>
              <TableHead>Credits/Op</TableHead>
              <TableHead>External Cost</TableHead>
              <TableHead className="w-[80px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pricing && pricing.length > 0 ? (
              pricing.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">{item.model_identifier}</TableCell>
                  <TableCell>{item.operation_type}</TableCell>
                  <TableCell>{item.credits_per_operation}</TableCell>
                  <TableCell>{formatCents(item.external_cost_cents)}</TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(item)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground">
                  No pricing entries configured.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingItem ? 'Edit Pricing' : 'Add Pricing'}
              </DialogTitle>
            </DialogHeader>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="model_identifier">Model Identifier</Label>
                <Input
                  id="model_identifier"
                  {...form.register('model_identifier')}
                  placeholder="e.g., gpt-4o"
                />
                {form.formState.errors.model_identifier && (
                  <p className="text-sm text-destructive">
                    {form.formState.errors.model_identifier.message}
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="operation_type">Operation Type</Label>
                <Input
                  id="operation_type"
                  {...form.register('operation_type')}
                  placeholder="e.g., generation"
                />
                {form.formState.errors.operation_type && (
                  <p className="text-sm text-destructive">
                    {form.formState.errors.operation_type.message}
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="credits_per_operation">Credits per Operation</Label>
                <Input
                  id="credits_per_operation"
                  type="number"
                  {...form.register('credits_per_operation', { valueAsNumber: true })}
                />
                {form.formState.errors.credits_per_operation && (
                  <p className="text-sm text-destructive">
                    {form.formState.errors.credits_per_operation.message}
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="external_cost_cents">External Cost (cents)</Label>
                <Input
                  id="external_cost_cents"
                  type="number"
                  {...form.register('external_cost_cents', { valueAsNumber: true })}
                />
                {form.formState.errors.external_cost_cents && (
                  <p className="text-sm text-destructive">
                    {form.formState.errors.external_cost_cents.message}
                  </p>
                )}
              </div>
              <DialogFooter>
                <Button type="submit" disabled={isPending}>
                  {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingItem ? 'Update' : 'Create'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}

function PacksSection() {
  const { data: packs, isLoading, isError, refetch } = usePacks();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Credit Packs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Credit Packs</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">Failed to load credit packs.</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Credit Packs</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Price</TableHead>
              <TableHead>Song Credits</TableHead>
              <TableHead>Request Count</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {packs && packs.length > 0 ? (
              packs.map((pack) => (
                <TableRow key={pack.id}>
                  <TableCell className="font-medium">{pack.name}</TableCell>
                  <TableCell>{formatCents(pack.price_cents)}</TableCell>
                  <TableCell>{pack.song_credits}</TableCell>
                  <TableCell>{pack.request_count}</TableCell>
                  <TableCell>
                    <Badge variant={pack.is_active ? 'default' : 'secondary'}>
                      {pack.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground">
                  No credit packs configured.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function BalanceAdjustmentSection() {
  const adjustBalance = useAdjustBalance();

  const form = useForm<CreditAdjustFormValues>({
    resolver: zodResolver(creditAdjustSchema),
    defaultValues: {
      user_id: '',
      amount: 0,
      reason: '',
    },
  });

  async function onSubmit(values: CreditAdjustFormValues) {
    await adjustBalance.mutateAsync(values);
    toast({ title: 'Balance adjusted successfully' });
    form.reset();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Balance Adjustment</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 max-w-md">
          <div className="space-y-2">
            <Label htmlFor="user_id">User ID</Label>
            <Input
              id="user_id"
              {...form.register('user_id')}
              placeholder="UUID of the user"
            />
            {form.formState.errors.user_id && (
              <p className="text-sm text-destructive">
                {form.formState.errors.user_id.message}
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="amount">Amount</Label>
            <Input
              id="amount"
              type="number"
              {...form.register('amount', { valueAsNumber: true })}
              placeholder="Positive to add, negative to deduct"
            />
            {form.formState.errors.amount && (
              <p className="text-sm text-destructive">
                {form.formState.errors.amount.message}
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="reason">Reason</Label>
            <Textarea
              id="reason"
              {...form.register('reason')}
              placeholder="Reason for adjustment"
            />
            {form.formState.errors.reason && (
              <p className="text-sm text-destructive">
                {form.formState.errors.reason.message}
              </p>
            )}
          </div>
          <Button type="submit" disabled={adjustBalance.isPending}>
            {adjustBalance.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Adjust Balance
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

// --- Page ---

export default function CreditsPage() {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Credits</h1>
      <PricingSection />
      <PacksSection />
      <BalanceAdjustmentSection />
    </div>
  );
}
