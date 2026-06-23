import { useState, useMemo } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AxiosError } from 'axios';
import { Loader2, Plus, Pencil, Trash2 } from 'lucide-react';

import {
  usePricing,
  useCreatePricing,
  useUpdatePricing,
  useDeletePricing,
  usePacks,
  useAdjustBalance,
  useServiceAvailability,
  useGlobalCreditValue,
  useUpdateGlobalCreditValue,
} from '@/hooks/use-credits';
import type { CreditPricing, ServiceAvailabilityEntry } from '@/types/models';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';

// --- Constants ---

const OPERATION_TYPES = [
  { value: 'music_generation', label: 'Music Generation' },
  { value: 'image_generation', label: 'Image Generation' },
  { value: 'text_generation', label: 'Text Generation' },
  { value: 'channel_setup', label: 'Channel Setup' },
] as const;

// --- Margin Computation ---

export function computeMargins(
  pricingCredits: number,
  costCredits: number,
  globalCreditValue: number | null,
) {
  if (globalCreditValue === null || globalCreditValue <= 0) {
    return { sellPriceDollars: null, costDollars: null, profitDollars: null, profitPercent: null };
  }
  const sellPriceDollars = pricingCredits * globalCreditValue;
  const costDollars = costCredits * globalCreditValue;
  const profitDollars = sellPriceDollars - costDollars;
  const profitPercent = sellPriceDollars > 0
    ? Math.round((profitDollars / sellPriceDollars) * 100 * 100) / 100
    : 0;
  return { sellPriceDollars, costDollars, profitDollars, profitPercent };
}

// --- Validation Schemas ---

const pricingFormSchema = z.object({
  ai_service: z.string().min(1, 'AI Service is required'),
  operation_type: z.string().min(1, 'Operation type is required'),
  credits_per_operation: z.number({ coerce: true }).min(1, 'Must be at least 1').max(10000, 'Pricing credits charged to customer'),
  external_cost_cents: z.number({ coerce: true }).min(0, 'Cost credits (what AI service costs us)'),
});

type PricingFormValues = z.infer<typeof pricingFormSchema>;

const gcvFormSchema = z.object({
  value: z
    .number({ coerce: true })
    .gt(0, 'Must be greater than 0')
    .lte(1.0, 'Must be at most 1.0'),
});

type GcvFormValues = z.infer<typeof gcvFormSchema>;

const creditAdjustSchema = z.object({
  user_id: z.string().uuid('Valid user ID is required'),
  amount: z.number({ coerce: true }).refine((v) => v !== 0, 'Amount must be non-zero'),
  reason: z
    .string()
    .min(1, 'Reason is required')
    .transform((v) => v.trim()),
});

type CreditAdjustFormValues = z.infer<typeof creditAdjustSchema>;

// --- Helpers ---

function formatDollars(dollars: number | null): string {
  if (dollars === null) return '—';
  return `$${dollars.toFixed(4)}`;
}

function formatPercent(percent: number | null): string {
  if (percent === null) return '—';
  return `${percent.toFixed(2)}%`;
}

function ServiceAvailabilityBadge({ status }: { status: string | undefined }) {
  if (!status) return null;

  const config = {
    available: { color: 'bg-green-500', label: 'Available' },
    degraded: { color: 'bg-yellow-500', label: 'Degraded' },
    unavailable: { color: 'bg-red-500', label: 'Unavailable' },
  }[status] ?? { color: 'bg-gray-500', label: status };

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2 w-2 rounded-full ${config.color}`} />
      <span className="text-xs text-muted-foreground">{config.label}</span>
    </span>
  );
}

// --- Components ---

function GlobalCreditValueSection() {
  const { data: gcvData, isLoading } = useGlobalCreditValue();
  const updateGcv = useUpdateGlobalCreditValue();

  const [packPrice, setPackPrice] = useState<string>('10');
  const [packCredits, setPackCredits] = useState<string>('3000');

  const derivedGcv = useMemo(() => {
    const price = parseFloat(packPrice);
    const credits = parseFloat(packCredits);
    if (!price || !credits || price <= 0 || credits <= 0) return null;
    return price / credits;
  }, [packPrice, packCredits]);

  const form = useForm<GcvFormValues>({
    resolver: zodResolver(gcvFormSchema),
    defaultValues: { value: gcvData?.global_credit_value ?? 0 },
  });

  // Sync form when data loads
  const currentGcv = gcvData?.global_credit_value;

  async function onSubmit(values: GcvFormValues) {
    try {
      await updateGcv.mutateAsync(values);
      toast({ title: 'Global Credit Value updated successfully' });
    } catch {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Failed to update Global Credit Value',
      });
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Global Credit Value</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Global Credit Value</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">Current value:</span>
          <span className="text-lg font-semibold">
            {currentGcv !== null && currentGcv !== undefined
              ? `$${currentGcv.toFixed(6)}`
              : 'Not configured'}
          </span>
        </div>

        {/* Update form */}
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 max-w-sm">
          <div className="space-y-2">
            <Label htmlFor="gcv-value">New Global Credit Value</Label>
            <Input
              id="gcv-value"
              type="number"
              step="0.000001"
              placeholder="e.g., 0.003333"
              {...form.register('value', { valueAsNumber: true })}
            />
            {form.formState.errors.value && (
              <p className="text-sm text-destructive">
                {form.formState.errors.value.message}
              </p>
            )}
          </div>
          <Button type="submit" size="sm" disabled={updateGcv.isPending}>
            {updateGcv.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Update
          </Button>
        </form>

        {/* Reference calculator */}
        <div className="border-t pt-4 space-y-3">
          <p className="text-sm font-medium">Reference Calculator</p>
          <p className="text-xs text-muted-foreground">
            If credit pack is $X for Y credits, then 1 credit = $Z
          </p>
          <div className="flex items-end gap-3 flex-wrap">
            <div className="space-y-1">
              <Label htmlFor="pack-price" className="text-xs">Pack Price ($)</Label>
              <Input
                id="pack-price"
                type="number"
                step="0.01"
                className="w-28"
                value={packPrice}
                onChange={(e) => setPackPrice(e.target.value)}
              />
            </div>
            <span className="text-muted-foreground pb-2">for</span>
            <div className="space-y-1">
              <Label htmlFor="pack-credits" className="text-xs">Credits</Label>
              <Input
                id="pack-credits"
                type="number"
                className="w-28"
                value={packCredits}
                onChange={(e) => setPackCredits(e.target.value)}
              />
            </div>
            <span className="text-muted-foreground pb-2">=</span>
            <div className="space-y-1">
              <Label className="text-xs">1 credit =</Label>
              <p className="h-10 flex items-center font-semibold text-sm">
                {derivedGcv !== null ? `$${derivedGcv.toFixed(6)}` : '—'}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function PricingSection() {
  const { data: pricing, isLoading, isError, refetch } = usePricing();
  const { data: serviceAvailability } = useServiceAvailability();
  const { data: gcvData } = useGlobalCreditValue();
  const createPricing = useCreatePricing();
  const updatePricing = useUpdatePricing();
  const deletePricing = useDeletePricing();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<CreditPricing | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<CreditPricing | null>(null);

  const globalCreditValue = gcvData?.global_credit_value ?? null;

  // Build a lookup map for service availability
  const availabilityMap = useMemo(() => {
    const map: Record<string, string> = {};
    if (serviceAvailability) {
      serviceAvailability.forEach((entry: ServiceAvailabilityEntry) => {
        map[entry.ai_service] = entry.status;
      });
    }
    return map;
  }, [serviceAvailability]);

  // Get AI services list from service availability
  const aiServices = useMemo(() => {
    if (!serviceAvailability) return [];
    return serviceAvailability.map((entry: ServiceAvailabilityEntry) => entry.ai_service);
  }, [serviceAvailability]);

  const form = useForm<PricingFormValues>({
    resolver: zodResolver(pricingFormSchema),
    defaultValues: {
      ai_service: '',
      operation_type: '',
      credits_per_operation: 1,
      external_cost_cents: 0,
    },
  });

  // Watch form values for real-time margin preview
  const watchedPricingCredits = useWatch({ control: form.control, name: 'credits_per_operation' });
  const watchedCostCredits = useWatch({ control: form.control, name: 'external_cost_cents' });

  const formMargins = useMemo(() => {
    const pricing = Number(watchedPricingCredits) || 0;
    const cost = Number(watchedCostCredits) || 0;
    return computeMargins(pricing, cost, globalCreditValue);
  }, [watchedPricingCredits, watchedCostCredits, globalCreditValue]);

  function openCreateDialog() {
    setEditingItem(null);
    form.reset({
      ai_service: '',
      operation_type: '',
      credits_per_operation: 1,
      external_cost_cents: 0,
    });
    setDialogOpen(true);
  }

  function openEditDialog(item: CreditPricing) {
    setEditingItem(item);
    form.reset({
      ai_service: item.ai_service || item.model_identifier,
      operation_type: item.operation_type,
      credits_per_operation: item.credits_per_operation,
      external_cost_cents: item.external_cost_cents ?? 0,
    });
    setDialogOpen(true);
  }

  async function handleDelete() {
    if (!deleteConfirm) return;
    try {
      await deletePricing.mutateAsync({
        ai_service: deleteConfirm.ai_service || deleteConfirm.model_identifier,
        operation_type: deleteConfirm.operation_type,
      });
      toast({ title: 'Pricing entry deleted' });
      setDeleteConfirm(null);
    } catch {
      toast({ variant: 'destructive', title: 'Failed to delete pricing entry' });
    }
  }

  async function onSubmit(values: PricingFormValues) {
    try {
      if (editingItem) {
        await updatePricing.mutateAsync(values);
        toast({ title: 'Pricing updated successfully' });
      } else {
        await createPricing.mutateAsync(values);
        toast({ title: 'Pricing created successfully' });
      }
      setDialogOpen(false);
    } catch (error) {
      if (error instanceof AxiosError && error.response?.status === 409) {
        toast({
          variant: 'destructive',
          title: 'Conflict',
          description: 'A pricing entry for this AI service/operation combination already exists',
        });
      }
    }
  }

  const isPending = createPricing.isPending || updatePricing.isPending;

  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>Pricing (Credit-Based)</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (<Skeleton key={i} className="h-10 w-full" />))}
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardHeader><CardTitle>Pricing (Credit-Based)</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">Failed to load pricing data.</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>Retry</Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Pricing (Credit-Based)</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Cost Credits = what the AI service costs us. Pricing Credits = what we charge the customer.
            </p>
          </div>
          <Button size="sm" onClick={openCreateDialog}>
            <Plus className="mr-1 h-4 w-4" />
            Add Pricing
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>AI Service</TableHead>
                <TableHead>Operation</TableHead>
                <TableHead>Cost Credits</TableHead>
                <TableHead>Pricing Credits</TableHead>
                <TableHead>Profit (credits)</TableHead>
                <TableHead>Cost ($)</TableHead>
                <TableHead>Revenue ($)</TableHead>
                <TableHead>Profit ($)</TableHead>
                <TableHead>Margin %</TableHead>
                <TableHead className="w-[100px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pricing && pricing.length > 0 ? (
                pricing.map((item) => {
                  const aiService = item.ai_service || item.model_identifier;
                  const costCredits = item.external_cost_cents ?? 0;
                  const pricingCredits = item.credits_per_operation;
                  const profitCredits = pricingCredits - costCredits;
                  const margins = computeMargins(pricingCredits, costCredits, globalCreditValue);
                  return (
                    <TableRow key={item.id}>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <span className="font-medium">{aiService}</span>
                          <ServiceAvailabilityBadge status={availabilityMap[aiService]} />
                        </div>
                      </TableCell>
                      <TableCell>
                        {OPERATION_TYPES.find((t) => t.value === item.operation_type)?.label ?? item.operation_type}
                      </TableCell>
                      <TableCell className="text-orange-400">{costCredits} cr</TableCell>
                      <TableCell className="text-blue-400">{pricingCredits} cr</TableCell>
                      <TableCell className={profitCredits >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {profitCredits >= 0 ? '+' : ''}{profitCredits} cr
                      </TableCell>
                      <TableCell>
                        {globalCreditValue !== null
                          ? formatDollars(margins.costDollars)
                          : <span className="text-muted-foreground text-xs">—</span>}
                      </TableCell>
                      <TableCell>
                        {globalCreditValue !== null
                          ? formatDollars(margins.sellPriceDollars)
                          : <span className="text-muted-foreground text-xs">—</span>}
                      </TableCell>
                      <TableCell>
                        {globalCreditValue !== null
                          ? <span className={margins.profitDollars! >= 0 ? 'text-green-400' : 'text-red-400'}>
                              {formatDollars(margins.profitDollars)}
                            </span>
                          : <span className="text-muted-foreground text-xs">—</span>}
                      </TableCell>
                      <TableCell>
                        {globalCreditValue !== null
                          ? formatPercent(margins.profitPercent)
                          : <span className="text-muted-foreground text-xs">—</span>}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm" onClick={() => openEditDialog(item)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-300" onClick={() => setDeleteConfirm(item)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              ) : (
                <TableRow>
                  <TableCell colSpan={10} className="text-center text-muted-foreground">
                    No pricing entries configured. Add one to start charging for AI operations.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingItem ? 'Edit Pricing' : 'Add Pricing'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label>AI Service</Label>
              <Select
                value={form.watch('ai_service')}
                onValueChange={(val) => form.setValue('ai_service', val, { shouldValidate: true })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select AI service" />
                </SelectTrigger>
                <SelectContent>
                  {aiServices.map((service) => (
                    <SelectItem key={service} value={service}>
                      <span className="flex items-center gap-2">
                        {service}
                        <ServiceAvailabilityBadge status={availabilityMap[service]} />
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {form.formState.errors.ai_service && (
                <p className="text-sm text-destructive">{form.formState.errors.ai_service.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label>Operation Type</Label>
              <Select
                value={form.watch('operation_type')}
                onValueChange={(val) => form.setValue('operation_type', val, { shouldValidate: true })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select operation type" />
                </SelectTrigger>
                <SelectContent>
                  {OPERATION_TYPES.map((op) => (
                    <SelectItem key={op.value} value={op.value}>{op.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {form.formState.errors.operation_type && (
                <p className="text-sm text-destructive">{form.formState.errors.operation_type.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="external_cost_cents">Cost Credits (what the AI service costs us)</Label>
              <Input
                id="external_cost_cents"
                type="number"
                {...form.register('external_cost_cents', { valueAsNumber: true })}
              />
              {form.formState.errors.external_cost_cents && (
                <p className="text-sm text-destructive">{form.formState.errors.external_cost_cents.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="credits_per_operation">Pricing Credits (what we charge the customer)</Label>
              <Input
                id="credits_per_operation"
                type="number"
                {...form.register('credits_per_operation', { valueAsNumber: true })}
              />
              {form.formState.errors.credits_per_operation && (
                <p className="text-sm text-destructive">{form.formState.errors.credits_per_operation.message}</p>
              )}
            </div>

            {/* Real-time margin preview */}
            <div className="border-t pt-3 space-y-2">
              <p className="text-sm font-medium text-muted-foreground">Margin Preview</p>
              <div className="grid grid-cols-4 gap-2 text-sm">
                <div>
                  <span className="text-xs text-muted-foreground">Profit (credits)</span>
                  <p className="font-medium">
                    {(Number(watchedPricingCredits) || 0) - (Number(watchedCostCredits) || 0)} cr
                  </p>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">Revenue ($)</span>
                  <p className="font-medium">
                    {globalCreditValue !== null ? formatDollars(formMargins.sellPriceDollars) : '—'}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">Profit ($)</span>
                  <p className="font-medium">
                    {globalCreditValue !== null ? formatDollars(formMargins.profitDollars) : '—'}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">Margin %</span>
                  <p className="font-medium">
                    {globalCreditValue !== null ? formatPercent(formMargins.profitPercent) : '—'}
                  </p>
                </div>
              </div>
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

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Pricing Entry</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to permanently delete the pricing entry for{' '}
            <strong>{deleteConfirm?.ai_service || deleteConfirm?.model_identifier}</strong> /{' '}
            <strong>{deleteConfirm?.operation_type}</strong>?
          </p>
          <p className="text-sm text-red-400">This action cannot be undone.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deletePricing.isPending}>
              {deletePricing.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
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
                  <TableCell>{formatDollars(pack.price_cents / 100)}</TableCell>
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
      <GlobalCreditValueSection />
      <PricingSection />
      <PacksSection />
      <BalanceAdjustmentSection />
    </div>
  );
}
