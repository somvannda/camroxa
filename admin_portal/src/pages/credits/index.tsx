import { useState, useMemo, useEffect } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AxiosError } from 'axios';
import { Loader2, Plus, Pencil, Trash2, Check } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

import {
  usePricing,
  useCreatePricing,
  useUpdatePricing,
  useDeletePricing,
  useDeleteAllPricing,
  useApprovePricing,
  useAdminCreditPacks,
  useCreateCreditPack,
  useUpdateCreditPack,
  useDeleteCreditPack,
  useAdjustBalance,
  useServiceAvailability,
  useGlobalCreditValue,
  useUpdateGlobalCreditValue,
} from '@/hooks/use-credits';
import type { CreditPack, CreditPricing, ServiceAvailabilityEntry } from '@/types/models';
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
import { ModelCostsSection } from '@/pages/credits/model-costs-section';
import { formatCredits, formatDollars } from '@/lib/credit-format';
import {
  computeMargins,
  marginFromPricing,
  pricingFromMargin,
} from '@/lib/credit-pricing-math';

// --- Constants ---

const OPERATION_TYPES = [
  // --- Specific operations (AI Model Routing) ---
  { value: 'channel_name', label: 'Channel Name' },
  { value: 'channel_description', label: 'Channel Description' },
  { value: 'channel_keywords', label: 'Channel Keywords' },
  { value: 'channel_tags', label: 'Channel Tags' },
  { value: 'channel_logo', label: 'Channel Logo' },
  { value: 'channel_cover', label: 'Channel Cover' },
  { value: 'lyric', label: 'Lyric' },
  { value: 'title', label: 'Title' },
  { value: 'album', label: 'Album' },
  { value: 'background_image', label: 'Background Image' },
  { value: 'thumbnail_image', label: 'Thumbnail Image' },
  { value: 'music', label: 'Music (Suno)' },
  { value: 'video', label: 'Video generation (local export)' },
  { value: 'video_merge', label: 'Auto merge video (local)' },
] as const;

// --- Validation Schemas ---

const pricingFormSchema = z.object({
  ai_service: z.string().min(1, 'AI Service is required'),
  operation_type: z.string().min(1, 'Operation type is required'),
  sub_model: z.string().optional(),
  credits_per_operation: z.number({ coerce: true }).min(0.0001, 'Minimum 0.0001 credit').max(10_000_000),
  external_cost_cents: z.number({ coerce: true }).min(0, 'Cost credits (what AI service costs us)'),
});

type PricingFormValues = z.infer<typeof pricingFormSchema>;

const packFormSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  price_dollars: z.number({ coerce: true }).min(0.5, 'Price must be at least $0.50'),
  song_credits: z.number({ coerce: true }).min(1, 'Must include at least 1 credit'),
  is_active: z.boolean().default(true),
});

type PackFormValues = z.infer<typeof packFormSchema>;

// Sub-model options per AI service with real API pricing (published, June 2025)
const SUB_MODEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  deepseek: [
    { value: 'deepseek-chat', label: 'deepseek-chat (~$0.0014/1K tokens)' },
    { value: 'deepseek-reasoner', label: 'deepseek-reasoner (~$0.0055/1K tokens)' },
  ],
  openai: [
    { value: 'gpt-4o-mini', label: 'gpt-4o-mini (~$0.0006/1K tokens)' },
    { value: 'gpt-4o', label: 'gpt-4o (~$0.01/1K tokens)' },
    { value: 'gpt-4-turbo', label: 'gpt-4-turbo (~$0.03/1K tokens)' },
    { value: 'gpt-image-1-mini', label: 'gpt-image-1-mini (~$0.02/img)' },
    { value: 'gpt-image-1', label: 'gpt-image-1 (~$0.04/img)' },
    { value: 'gpt-image-1.5', label: 'gpt-image-1.5 (~$0.07/img)' },
    { value: 'gpt-image-2', label: 'gpt-image-2 (~$0.19/img)' },
  ],
  fal: [
    { value: 'flux-schnell', label: 'flux-schnell (~$0.003/img)' },
    { value: 'flux-dev', label: 'flux-dev (~$0.025/img)' },
    { value: 'flux-pro', label: 'flux-pro (~$0.05/img)' },
  ],
  slai: [
    { value: 'xiaomi/mimo-v2.5-pro', label: 'xiaomi/mimo-v2.5-pro (SLAI MiMo text)' },
    { value: 'slai/gpt-image-2', label: 'slai/gpt-image-2 (SLAI images)' },
  ],
  local: [],
  cala: [],
  suno: [
    { value: 'V5', label: 'V5' },
    { value: 'V5_5', label: 'V5.5' },
    { value: 'lyrics', label: 'lyrics (Suno lyric API)' },
  ],
};

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

function formatPercent(percent: number | null): string {
  if (percent === null || !Number.isFinite(percent)) return '—';
  return `${percent.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
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
  const [packCredits, setPackCredits] = useState<string>('1000');

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
            <p className="text-sm text-muted-foreground mt-1">
              Recommended: $0.01 (1 credit = 1 cent, $10 = 1,000 credits).
            </p>
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
            <p className="text-sm text-muted-foreground mt-1">
              Recommended: $0.01 (1 credit = 1 cent, $10 = 1,000 credits).
            </p>
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
              1 credit = $0.01 when GCV is $0.01 ($10 pack → 1,000 credits).
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
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: pricing, isLoading, isError, refetch } = usePricing();
  const { data: serviceAvailability } = useServiceAvailability();
  const { data: gcvData } = useGlobalCreditValue();
  const createPricing = useCreatePricing();
  const updatePricing = useUpdatePricing();
  const deletePricing = useDeletePricing();
  const deleteAllPricing = useDeleteAllPricing();
  const approvePricing = useApprovePricing();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<CreditPricing | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<CreditPricing | null>(null);
  const [deleteAllConfirmOpen, setDeleteAllConfirmOpen] = useState(false);
  const [targetMarginPercent, setTargetMarginPercent] = useState('50');
  const [providerFilter, setProviderFilter] = useState<string>('all');
  const [reviewFilter, setReviewFilter] = useState<'all' | 'needs_review'>(
    searchParams.get('filter') === 'needs_review' ? 'needs_review' : 'all',
  );

  useEffect(() => {
    if (searchParams.get('filter') === 'needs_review') {
      setReviewFilter('needs_review');
    }
  }, [searchParams]);

  const globalCreditValue = gcvData?.global_credit_value ?? null;
  const draftCount = useMemo(
    () => (pricing ?? []).filter((item) => item.needs_review).length,
    [pricing],
  );

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

  // Get AI services list from service availability (+ local desktop ops)
  const aiServices = useMemo(() => {
    const services = serviceAvailability
      ? serviceAvailability.map((entry: ServiceAvailabilityEntry) => entry.ai_service)
      : [];
    if (!services.includes('local')) {
      services.push('local');
    }
    return services.sort();
  }, [serviceAvailability]);

  const form = useForm<PricingFormValues>({
    resolver: zodResolver(pricingFormSchema),
    defaultValues: {
      ai_service: '',
      operation_type: '',
      sub_model: '',
      credits_per_operation: 0.05,
      external_cost_cents: 0.03,
    },
  });

  // Watch form values for real-time margin preview
  const watchedPricingCredits = useWatch({ control: form.control, name: 'credits_per_operation' });
  const watchedCostCredits = useWatch({ control: form.control, name: 'external_cost_cents' });
  const costCreditsField = form.register('external_cost_cents', { valueAsNumber: true });
  const pricingCreditsField = form.register('credits_per_operation', { valueAsNumber: true });

  const formMargins = useMemo(() => {
    const pricing = Number(watchedPricingCredits) || 0;
    const cost = Number(watchedCostCredits) || 0;
    return computeMargins(pricing, cost, globalCreditValue);
  }, [watchedPricingCredits, watchedCostCredits, globalCreditValue]);

  function applyMarginToPricing(costCredits: number, marginText: string) {
    const margin = Number(marginText);
    if (!Number.isFinite(margin) || margin < 0) return;
    form.setValue(
      'credits_per_operation',
      pricingFromMargin(costCredits, margin),
      { shouldValidate: true },
    );
  }

  function syncMarginFromPricing(costCredits: number, pricingCredits: number) {
    setTargetMarginPercent(String(marginFromPricing(costCredits, pricingCredits)));
  }

  function openCreateDialog() {
    setEditingItem(null);
    const cost = 0.03;
    const pricing = 0.05;
    form.reset({
      ai_service: '',
      operation_type: '',
      sub_model: '',
      credits_per_operation: pricing,
      external_cost_cents: cost,
    });
    setTargetMarginPercent(String(marginFromPricing(cost, pricing)));
    setDialogOpen(true);
  }

  function openEditDialog(item: CreditPricing) {
    setEditingItem(item);
    const cost = item.external_cost_cents ?? 0;
    const pricing = item.credits_per_operation;
    form.reset({
      ai_service: item.ai_service || item.model_identifier,
      operation_type: item.operation_type,
      sub_model: item.sub_model ?? '',
      credits_per_operation: pricing,
      external_cost_cents: cost,
    });
    setTargetMarginPercent(String(marginFromPricing(cost, pricing)));
    setDialogOpen(true);
  }

  async function handleDelete() {
    if (!deleteConfirm) return;
    try {
      await deletePricing.mutateAsync({
        ai_service: deleteConfirm.ai_service || deleteConfirm.model_identifier,
        operation_type: deleteConfirm.operation_type,
        sub_model: deleteConfirm.sub_model ?? '',
      });
      toast({ title: 'Pricing entry deleted' });
      setDeleteConfirm(null);
    } catch {
      toast({ variant: 'destructive', title: 'Failed to delete pricing entry' });
    }
  }

  async function handleDeleteAll() {
    const scopeProvider = providerFilter !== 'all' ? providerFilter : undefined;
    try {
      const result = await deleteAllPricing.mutateAsync(scopeProvider);
      toast({
        title: 'Pricing cleared',
        description: `Deleted ${result.deleted_count} row(s). Use Model Costs → Auto-generate pricing to rebuild.`,
      });
      setDeleteAllConfirmOpen(false);
    } catch {
      toast({ variant: 'destructive', title: 'Failed to delete pricing rows' });
    }
  }

  async function onSubmit(values: PricingFormValues) {
    try {
      if (editingItem) {
        await updatePricing.mutateAsync({
          ...values,
          lookup_sub_model: editingItem.sub_model ?? '',
        });
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
          description: 'A pricing entry for this provider/operation/model already exists',
        });
      } else if (error instanceof AxiosError && error.response?.status === 404) {
        toast({
          variant: 'destructive',
          title: 'Pricing row not found',
          description: 'Try refreshing the page. The row key may have changed after model-aware pricing.',
        });
      }
    }
  }

  async function handleApprove(item: CreditPricing) {
    try {
      await approvePricing.mutateAsync({
        ai_service: item.ai_service || item.model_identifier,
        operation_type: item.operation_type,
        entries: [
          {
            ai_service: item.ai_service || item.model_identifier,
            operation_type: item.operation_type,
            sub_model: item.sub_model ?? '',
          },
        ],
      });
      toast({ title: 'Pricing approved' });
    } catch {
      toast({ variant: 'destructive', title: 'Failed to approve pricing' });
    }
  }

  function setReviewFilterAndUrl(next: 'all' | 'needs_review') {
    setReviewFilter(next);
    if (next === 'needs_review') {
      setSearchParams({ filter: 'needs_review' });
    } else {
      setSearchParams({});
    }
  }

  const isPending = createPricing.isPending || updatePricing.isPending;

  // Filter pricing by provider tab and review status
  const filteredPricing = useMemo(() => {
    if (!pricing) return [];
    return pricing.filter((item) => {
      const service = item.ai_service || item.model_identifier;
      if (providerFilter !== 'all' && service !== providerFilter) return false;
      if (reviewFilter === 'needs_review' && !item.needs_review) return false;
      return true;
    });
  }, [pricing, providerFilter, reviewFilter]);

  async function handleApproveVisibleDrafts() {
    const drafts = filteredPricing.filter((item) => item.needs_review);
    if (drafts.length === 0) return;
    try {
      const result = await approvePricing.mutateAsync({
        entries: drafts.map((item) => ({
          ai_service: item.ai_service || item.model_identifier,
          operation_type: item.operation_type,
          sub_model: item.sub_model ?? '',
        })),
      }) as { approved_count?: number };
      toast({
        title: `Approved ${result.approved_count ?? drafts.length} draft price(s)`,
      });
    } catch {
      toast({ variant: 'destructive', title: 'Failed to approve draft pricing' });
    }
  }

  // Get unique providers from pricing data for tabs
  const providerTabs = useMemo(() => {
    if (!pricing) return [];
    const providers = new Set(pricing.map((item) => item.ai_service || item.model_identifier));
    return Array.from(providers).sort();
  }, [pricing]);

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
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="border-red-800 text-red-300 hover:bg-red-950/40"
              onClick={() => setDeleteAllConfirmOpen(true)}
              disabled={!pricing?.length}
            >
              <Trash2 className="mr-1 h-4 w-4" />
              {providerFilter !== 'all' ? `Delete all (${providerFilter})` : 'Delete all'}
            </Button>
            <Button size="sm" onClick={openCreateDialog}>
              <Plus className="mr-1 h-4 w-4" />
              Add Pricing
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {draftCount > 0 && (
            <div className="mb-4 rounded-lg border border-red-800/60 bg-red-950/20 p-3 text-sm text-red-200">
              <span className="font-medium">{draftCount} draft price(s)</span> auto-created from
              AI routing need margin review. Adjust cost/pricing credits, then approve.
            </div>
          )}
          <div className="flex gap-1 mb-4 flex-wrap items-center">
            <Button
              variant={reviewFilter === 'all' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setReviewFilterAndUrl('all')}
            >
              All rows
            </Button>
            <Button
              variant={reviewFilter === 'needs_review' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setReviewFilterAndUrl('needs_review')}
              className={draftCount > 0 ? 'border-red-500/50' : undefined}
            >
              Needs review
              {draftCount > 0 ? ` (${draftCount})` : ''}
            </Button>
            {reviewFilter === 'needs_review' && filteredPricing.some((item) => item.needs_review) && (
              <Button
                variant="outline"
                size="sm"
                className="ml-auto border-emerald-600 text-emerald-300"
                onClick={handleApproveVisibleDrafts}
                disabled={approvePricing.isPending}
              >
                {approvePricing.isPending ? (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                ) : (
                  <Check className="mr-1 h-4 w-4" />
                )}
                Approve visible
              </Button>
            )}
          </div>
          {/* Provider filter tabs */}
          <div className="flex gap-1 mb-4 flex-wrap">
            <Button
              variant={providerFilter === 'all' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setProviderFilter('all')}
            >
              All
            </Button>
            {providerTabs.map((provider) => (
              <Button
                key={provider}
                variant={providerFilter === provider ? 'default' : 'outline'}
                size="sm"
                onClick={() => setProviderFilter(provider)}
                className="capitalize"
              >
                {provider}
              </Button>
            ))}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>AI Service</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Operation</TableHead>
                <TableHead>Cost Credits</TableHead>
                <TableHead>Pricing Credits</TableHead>
                <TableHead>Profit (credits)</TableHead>
                <TableHead>Cost ($)</TableHead>
                <TableHead>Revenue ($)</TableHead>
                <TableHead>Profit ($)</TableHead>
                <TableHead>Margin % (on cost)</TableHead>
                <TableHead>Charge</TableHead>
                <TableHead className="w-[100px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredPricing && filteredPricing.length > 0 ? (
                filteredPricing.map((item) => {
                  const aiService = item.ai_service || item.model_identifier;
                  const costCredits = item.external_cost_cents ?? 0;
                  const pricingCredits = item.credits_per_operation;
                  const profitCredits = pricingCredits - costCredits;
                  const margins = computeMargins(pricingCredits, costCredits, globalCreditValue);
                  return (
                    <TableRow
                      key={item.id}
                      className={item.needs_review ? 'bg-red-950/20 border-l-2 border-l-red-500' : undefined}
                    >
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <span className="font-medium">{aiService}</span>
                          <div className="flex flex-wrap items-center gap-2">
                            <ServiceAvailabilityBadge status={availabilityMap[aiService]} />
                            {item.needs_review && (
                              <Badge variant="destructive" className="text-xs">
                                Needs review
                              </Badge>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-sm">
                          {item.sub_model ? item.sub_model : (
                            <span className="text-muted-foreground italic">Default (all models)</span>
                          )}
                        </span>
                      </TableCell>
                      <TableCell>
                        {OPERATION_TYPES.find((t) => t.value === item.operation_type)?.label ?? item.operation_type}
                      </TableCell>
                      <TableCell className="text-orange-400">{formatCredits(costCredits)} cr</TableCell>
                      <TableCell className="text-blue-400">{formatCredits(pricingCredits)} cr</TableCell>
                      <TableCell className={profitCredits >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {profitCredits >= 0 ? '+' : ''}{formatCredits(profitCredits)} cr
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
                      <TableCell className="font-medium text-emerald-400">
                        {formatPercent(margins.profitPercentOnCost)}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {margins.chargeMultiplier != null
                          ? `${margins.chargeMultiplier}× cost`
                          : '—'}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {item.needs_review && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-emerald-400 hover:text-emerald-300"
                              title="Approve pricing"
                              onClick={() => handleApprove(item)}
                            >
                              <Check className="h-4 w-4" />
                            </Button>
                          )}
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
                  <TableCell colSpan={11} className="text-center text-muted-foreground">
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
                disabled={!!editingItem}
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
                disabled={!!editingItem}
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
            {/* Sub-model (optional, shows cost tier hints) */}
            {(SUB_MODEL_OPTIONS[form.watch('ai_service')] ?? []).length > 0 ? (
              <div className="space-y-2">
                <Label>Sub-Model <span className="text-muted-foreground text-xs">(optional — for per-model pricing)</span></Label>
                {editingItem ? (
                  <p className="text-sm font-mono py-2">
                    {editingItem.sub_model
                      ? editingItem.sub_model
                      : <span className="text-muted-foreground italic">Default (all models)</span>}
                  </p>
                ) : (
                <Select
                  value={form.watch('sub_model') || '__default__'}
                  onValueChange={(val) => form.setValue('sub_model', val === '__default__' ? '' : val)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All models (default)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__default__">Default (all models)</SelectItem>
                    {(SUB_MODEL_OPTIONS[form.watch('ai_service')] ?? []).map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                )}
                {form.watch('ai_service') === 'suno' && (
                  <p className="text-xs text-muted-foreground">
                    Use operation <strong>Music Generation (Suno billing)</strong> for song generation.
                    Set a separate price for each Suno model, or leave default for provider-wide pricing.
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <Label>Sub-Model <span className="text-muted-foreground text-xs">(optional)</span></Label>
                <Input
                  {...form.register('sub_model')}
                  placeholder="Leave empty for provider default"
                  disabled={!!editingItem}
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="external_cost_cents">Cost Credits (what the AI service costs us)</Label>
              <Input
                id="external_cost_cents"
                type="number"
                step="0.0001"
                min={0}
                name={costCreditsField.name}
                ref={costCreditsField.ref}
                onBlur={costCreditsField.onBlur}
                value={watchedCostCredits ?? ''}
                onChange={(event) => {
                  costCreditsField.onChange(event);
                  const cost = Number(event.target.value) || 0;
                  applyMarginToPricing(cost, targetMarginPercent);
                }}
              />
              {form.formState.errors.external_cost_cents && (
                <p className="text-sm text-destructive">{form.formState.errors.external_cost_cents.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="target_margin_percent">
                Margin % <span className="text-muted-foreground text-xs">(on cost)</span>
              </Label>
              <Input
                id="target_margin_percent"
                type="number"
                step="any"
                min={0}
                value={targetMarginPercent}
                onChange={(event) => {
                  const next = event.target.value;
                  setTargetMarginPercent(next);
                  const cost = Number(form.getValues('external_cost_cents')) || 0;
                  applyMarginToPricing(cost, next);
                }}
              />
              <p className="text-xs text-muted-foreground">
                Profit as % of your cost. 100% = earn the same as cost (charge 2×).
                1000% = earn 10× cost (charge 11×). This is not margin on revenue.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="credits_per_operation">Pricing Credits (what we charge the customer)</Label>
              <Input
                id="credits_per_operation"
                type="number"
                step="0.0001"
                min={0.0001}
                name={pricingCreditsField.name}
                ref={pricingCreditsField.ref}
                onBlur={pricingCreditsField.onBlur}
                value={watchedPricingCredits ?? ''}
                onChange={(event) => {
                  pricingCreditsField.onChange(event);
                  const pricing = Number(event.target.value) || 0;
                  const cost = Number(form.getValues('external_cost_cents')) || 0;
                  syncMarginFromPricing(cost, pricing);
                }}
              />
              {form.formState.errors.credits_per_operation && (
                <p className="text-sm text-destructive">{form.formState.errors.credits_per_operation.message}</p>
              )}
            </div>

            <div className="border-t pt-3 space-y-2">
              <p className="text-sm font-medium text-muted-foreground">Preview</p>
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                <div>
                  <span className="text-xs text-muted-foreground">Margin % (on cost)</span>
                  <p className="font-medium text-emerald-400">
                    {formatPercent(formMargins.profitPercentOnCost)}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    {formMargins.chargeMultiplier != null
                      ? `Charge ${formMargins.chargeMultiplier}× cost`
                      : null}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">Profit (credits)</span>
                  <p className="font-medium">
                    {formatCredits((Number(watchedPricingCredits) || 0) - (Number(watchedCostCredits) || 0))} cr
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    cost {formatCredits(Number(watchedCostCredits) || 0)} → price{' '}
                    {formatCredits(Number(watchedPricingCredits) || 0)}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground">Profit ($)</span>
                  <p className="font-medium">
                    {globalCreditValue !== null ? formatDollars(formMargins.profitDollars) : '—'}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    revenue {globalCreditValue !== null ? formatDollars(formMargins.sellPriceDollars) : '—'}
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

      <Dialog open={deleteAllConfirmOpen} onOpenChange={setDeleteAllConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {providerFilter !== 'all'
                ? `Delete all ${providerFilter} pricing`
                : 'Delete all pricing'}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {providerFilter !== 'all' ? (
              <>
                Permanently delete every pricing row for <strong>{providerFilter}</strong>.
              </>
            ) : (
              <>Permanently delete every pricing row across all providers.</>
            )}{' '}
            You can rebuild from Model Costs using <strong>Auto-generate pricing</strong>.
          </p>
          <p className="text-sm text-red-400">This action cannot be undone.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteAllConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteAll}
              disabled={deleteAllPricing.isPending}
            >
              {deleteAllPricing.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete all
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function PacksSection() {
  const { data: packs, isLoading, isError, refetch } = useAdminCreditPacks();
  const { data: gcvData } = useGlobalCreditValue();
  const createPack = useCreateCreditPack();
  const updatePack = useUpdateCreditPack();
  const deletePack = useDeleteCreditPack();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPack, setEditingPack] = useState<CreditPack | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<CreditPack | null>(null);

  const globalCreditValue = gcvData?.global_credit_value ?? null;

  const form = useForm<PackFormValues>({
    resolver: zodResolver(packFormSchema),
    defaultValues: {
      name: '',
      price_dollars: 10,
      song_credits: 1000,
      is_active: true,
    },
  });

  const watchedPrice = useWatch({ control: form.control, name: 'price_dollars' });
  const watchedCredits = useWatch({ control: form.control, name: 'song_credits' });

  const impliedGcv = useMemo(() => {
    const price = Number(watchedPrice) || 0;
    const credits = Number(watchedCredits) || 0;
    if (!price || !credits) return null;
    return price / credits;
  }, [watchedPrice, watchedCredits]);

  function openCreateDialog() {
    setEditingPack(null);
    form.reset({
      name: '',
      price_dollars: 10,
      song_credits: 1000,
      is_active: true,
    });
    setDialogOpen(true);
  }

  function openEditDialog(pack: CreditPack) {
    setEditingPack(pack);
    form.reset({
      name: pack.name,
      price_dollars: pack.price_cents / 100,
      song_credits: pack.song_credits,
      is_active: pack.is_active,
    });
    setDialogOpen(true);
  }

  async function onSubmit(values: PackFormValues) {
    const payload = {
      name: values.name,
      price_cents: Math.round(values.price_dollars * 100),
      song_credits: values.song_credits,
      is_active: values.is_active,
    };
    try {
      if (editingPack) {
        await updatePack.mutateAsync({ id: editingPack.id, ...payload });
        toast({ title: 'Credit pack updated' });
      } else {
        await createPack.mutateAsync(payload);
        toast({ title: 'Credit pack created' });
      }
      setDialogOpen(false);
    } catch {
      toast({ variant: 'destructive', title: 'Failed to save credit pack' });
    }
  }

  async function handleDelete() {
    if (!deleteConfirm) return;
    try {
      await deletePack.mutateAsync(deleteConfirm.id);
      toast({ title: 'Credit pack deleted' });
      setDeleteConfirm(null);
    } catch {
      toast({ variant: 'destructive', title: 'Failed to delete credit pack' });
    }
  }

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
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Credit Packs</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              One-time wallet top-ups for sale. Users buy credits; AI operations deduct from the wallet.
            </p>
          </div>
          <Button size="sm" onClick={openCreateDialog}>
            <Plus className="mr-1 h-4 w-4" />
            Add Pack
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Credits</TableHead>
                <TableHead>$/Credit</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-[100px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {packs && packs.length > 0 ? (
                packs.map((pack) => {
                  const perCredit =
                    globalCreditValue !== null
                      ? pack.price_cents / 100 / pack.song_credits
                      : pack.price_cents / 100 / pack.song_credits;
                  return (
                    <TableRow key={pack.id}>
                      <TableCell className="font-medium">{pack.name}</TableCell>
                      <TableCell>{formatDollars(pack.price_cents / 100)}</TableCell>
                      <TableCell>{formatCredits(pack.song_credits)} cr</TableCell>
                      <TableCell>{formatDollars(perCredit)}</TableCell>
                      <TableCell>
                        <Badge variant={pack.is_active ? 'default' : 'secondary'}>
                          {pack.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm" onClick={() => openEditDialog(pack)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-400 hover:text-red-300"
                            onClick={() => setDeleteConfirm(pack)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No credit packs configured. Add one to sell wallet top-ups.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingPack ? 'Edit Credit Pack' : 'Add Credit Pack'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="pack-name">Pack name</Label>
              <Input id="pack-name" {...form.register('name')} placeholder="Starter Pack" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pack-price">Sale price ($)</Label>
                <Input
                  id="pack-price"
                  type="number"
                  step="0.01"
                  {...form.register('price_dollars', { valueAsNumber: true })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pack-credits">Credits included</Label>
                <Input
                  id="pack-credits"
                  type="number"
                  {...form.register('song_credits', { valueAsNumber: true })}
                />
              </div>
            </div>
            <div className="rounded-md border border-slate-700 p-3 text-sm text-muted-foreground">
              Implied value:{' '}
              <span className="font-medium text-slate-200">
                {impliedGcv !== null ? `$${impliedGcv.toFixed(6)} / credit` : '—'}
              </span>
              {globalCreditValue !== null && impliedGcv !== null ? (
                <span className="block text-xs mt-1">
                  Platform GCV: ${globalCreditValue.toFixed(6)} / credit
                </span>
              ) : null}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.watch('is_active')}
                onChange={(event) => form.setValue('is_active', event.target.checked)}
              />
              Active (visible for purchase)
            </label>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createPack.isPending || updatePack.isPending}>
                {(createPack.isPending || updatePack.isPending) && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {editingPack ? 'Save changes' : 'Create pack'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteConfirm} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete credit pack</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Delete <strong>{deleteConfirm?.name}</strong>? This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deletePack.isPending}>
              {deletePack.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
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
    const result = await adjustBalance.mutateAsync(values);
    const pending =
      result &&
      typeof result === 'object' &&
      'requires_approval' in result &&
      Boolean((result as { requires_approval?: boolean }).requires_approval);
    toast({
      title: pending
        ? 'Queued for dual-control approval'
        : 'Balance adjusted successfully',
      description: pending
        ? 'A second admin must approve this large adjustment before it applies.'
        : undefined,
    });
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
      <ModelCostsSection />
      <PricingSection />
      <PacksSection />
      <BalanceAdjustmentSection />
    </div>
  );
}
