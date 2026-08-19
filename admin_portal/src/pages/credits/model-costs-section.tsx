import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, Plus, Pencil, Trash2, Sparkles } from 'lucide-react';

import {
  useModelCosts,
  useCreateModelCost,
  useUpdateModelCost,
  useDeleteModelCost,
  useSeedModelCosts,
  useGeneratePricing,
  useRegistryPricingGaps,
  useSeedRegistryPricing,
  useGlobalCreditValue,
} from '@/hooks/use-credits';
import type { ModelCost } from '@/types/models';
import { toast } from '@/hooks/use-toast';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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

const OPERATION_TYPES = [
  { value: 'channel_name', label: 'Channel Name' },
  { value: 'channel_description', label: 'Channel Description' },
  { value: 'channel_keywords', label: 'Channel Keywords' },
  { value: 'channel_tags', label: 'Channel Tags' },
  { value: 'channel_logo', label: 'Channel Logo' },
  { value: 'channel_cover', label: 'Channel Cover' },
  { value: 'lyric', label: 'Lyric (Desktop / Batch)' },
  { value: 'web_music_lyrics', label: 'Music Lyric' },
  { value: 'web_music_style', label: 'Music Style Tags' },
  { value: 'title', label: 'Title' },
  { value: 'album', label: 'Album' },
  { value: 'background_image', label: 'Background Image' },
  { value: 'thumbnail_image', label: 'Thumbnail Image' },
  { value: 'music', label: 'Music' },
] as const;

const costFormSchema = z.object({
  ai_service: z.string().min(1),
  operation_type: z.string().min(1),
  sub_model: z.string().optional(),
  cost_usd: z.number({ coerce: true }).min(0),
  notes: z.string().optional(),
});

type CostFormValues = z.infer<typeof costFormSchema>;

function formatUsd(amount: number) {
  if (amount === 0) return '$0';
  if (amount < 0.01) return `$${amount.toFixed(6).replace(/0+$/, '').replace(/\.$/, '')}`;
  if (amount < 1) return `$${amount.toFixed(4)}`;
  return `$${amount.toFixed(2)}`;
}

export function ModelCostsSection() {
  const { data: costs, isLoading, isError, refetch } = useModelCosts();
  const { data: gcvData } = useGlobalCreditValue();
  const createCost = useCreateModelCost();
  const updateCost = useUpdateModelCost();
  const deleteCost = useDeleteModelCost();
  const seedCosts = useSeedModelCosts();
  const generatePricing = useGeneratePricing();
  const { data: registryGaps } = useRegistryPricingGaps();
  const seedRegistryPricing = useSeedRegistryPricing();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [registryPricingOpen, setRegistryPricingOpen] = useState(false);
  const [editing, setEditing] = useState<ModelCost | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ModelCost | null>(null);
  const [marginPercent, setMarginPercent] = useState('10');
  const [overwriteExisting, setOverwriteExisting] = useState(false);
  const [providerFilter, setProviderFilter] = useState('all');
  const [modelFilter, setModelFilter] = useState('all');

  const form = useForm<CostFormValues>({
    resolver: zodResolver(costFormSchema),
    defaultValues: {
      ai_service: '',
      operation_type: '',
      sub_model: '',
      cost_usd: 0.0001,
      notes: '',
    },
  });

  const providerTabs = useMemo(() => {
    if (!costs) return [];
    return Array.from(new Set(costs.map((c) => c.ai_service))).sort();
  }, [costs]);

  const modelOptions = useMemo(() => {
    if (!costs) return [];
    const scoped = providerFilter === 'all'
      ? costs
      : costs.filter((c) => c.ai_service === providerFilter);
    const models = new Set(scoped.map((c) => c.sub_model || ''));
    return Array.from(models).sort((a, b) => {
      if (a === '') return -1;
      if (b === '') return 1;
      return a.localeCompare(b);
    });
  }, [costs, providerFilter]);

  const filteredCosts = useMemo(() => {
    if (!costs) return [];
    return costs.filter((item) => {
      if (providerFilter !== 'all' && item.ai_service !== providerFilter) return false;
      if (modelFilter !== 'all') {
        const itemModel = item.sub_model || '';
        if (itemModel !== modelFilter) return false;
      }
      return true;
    });
  }, [costs, providerFilter, modelFilter]);

  function openCreate() {
    setEditing(null);
    form.reset({
      ai_service: providerFilter !== 'all' ? providerFilter : '',
      operation_type: '',
      sub_model: modelFilter !== 'all' ? modelFilter : '',
      cost_usd: 0.0001,
      notes: '',
    });
    setDialogOpen(true);
  }

  function openEdit(item: ModelCost) {
    setEditing(item);
    form.reset({
      ai_service: item.ai_service,
      operation_type: item.operation_type,
      sub_model: item.sub_model ?? '',
      cost_usd: item.cost_usd,
      notes: item.notes ?? '',
    });
    setDialogOpen(true);
  }

  async function onSubmit(values: CostFormValues) {
    try {
      if (editing) {
        await updateCost.mutateAsync(values);
        toast({ title: 'Model cost updated' });
      } else {
        await createCost.mutateAsync(values);
        toast({ title: 'Model cost created' });
      }
      setDialogOpen(false);
    } catch {
      toast({ variant: 'destructive', title: 'Failed to save model cost' });
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteCost.mutateAsync({
        ai_service: deleteTarget.ai_service,
        operation_type: deleteTarget.operation_type,
        sub_model: deleteTarget.sub_model ?? '',
      });
      toast({ title: 'Model cost deleted' });
      setDeleteTarget(null);
    } catch {
      toast({ variant: 'destructive', title: 'Failed to delete model cost' });
    }
  }

  async function handleSeed(overwrite = false) {
    try {
      const result = await seedCosts.mutateAsync(overwrite) as {
        seeded_count?: number;
        skipped_existing_count?: number;
        pruned_count?: number;
        local_pricing_created_count?: number;
        local_pricing_updated_count?: number;
        local_pricing_skipped_count?: number;
      };
      toast({
        title: overwrite
          ? `Updated ${result.seeded_count} model cost(s)`
          : `Seeded ${result.seeded_count} model cost(s)`,
        description: [
          result.skipped_existing_count
            ? `${result.skipped_existing_count} cost row(s) already existed`
            : null,
          result.pruned_count ? `${result.pruned_count} stale cost row(s) removed` : null,
          result.local_pricing_created_count
            ? `${result.local_pricing_created_count} local pricing row(s) added (video/merge)`
            : null,
          result.local_pricing_skipped_count
            ? `${result.local_pricing_skipped_count} local pricing row(s) kept as-is`
            : null,
          overwrite ? 'Registry estimates overwrote matching cost rows.' : null,
        ]
          .filter(Boolean)
          .join(' · ') || undefined,
      });
    } catch {
      toast({ variant: 'destructive', title: 'Failed to seed model costs' });
    }
  }

  async function handleGenerate() {
    const margin = Number(marginPercent);
    if (!Number.isFinite(margin) || margin < 0 || margin >= 100) {
      toast({ variant: 'destructive', title: 'Enter a margin between 0 and 99' });
      return;
    }
    if (!gcvData?.global_credit_value) {
      toast({
        variant: 'destructive',
        title: 'Set Global Credit Value first',
        description: 'Pricing generation needs GCV to convert USD costs into credits.',
      });
      return;
    }
    try {
      const result = await generatePricing.mutateAsync({
        margin_percent: margin,
        overwrite_existing: overwriteExisting,
        mark_needs_review: true,
      }) as {
        created_count?: number;
        updated_count?: number;
        missing_cost_count?: number;
      };
      toast({
        title: 'Pricing generated',
        description: `Created ${result.created_count ?? 0}, updated ${result.updated_count ?? 0}. Missing costs: ${result.missing_cost_count ?? 0}.`,
      });
      setGenerateOpen(false);
    } catch {
      toast({ variant: 'destructive', title: 'Failed to generate pricing' });
    }
  }

  async function handleSeedRegistryPricing() {
    const margin = Number(marginPercent);
    if (!Number.isFinite(margin) || margin < 0 || margin >= 100) {
      toast({ variant: 'destructive', title: 'Enter a margin between 0 and 99' });
      return;
    }
    if (!gcvData?.global_credit_value) {
      toast({
        variant: 'destructive',
        title: 'Set Global Credit Value first',
      });
      return;
    }
    try {
      const result = await seedRegistryPricing.mutateAsync({
        margin_percent: margin,
      }) as {
        created_count?: number;
        skipped_existing_count?: number;
        missing_cost_count?: number;
      };
      toast({
        title: 'Registry pricing drafts created',
        description: `Added ${result.created_count ?? 0} needs-review row(s). Skipped ${result.skipped_existing_count ?? 0} existing. Missing costs: ${result.missing_cost_count ?? 0}.`,
      });
      setRegistryPricingOpen(false);
    } catch {
      toast({ variant: 'destructive', title: 'Failed to seed registry pricing' });
    }
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <div>
            <CardTitle>Model Costs (USD)</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Base provider cost per model and operation. Used to auto-generate customer pricing from your target margin.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => handleSeed(false)} disabled={seedCosts.isPending}>
              {seedCosts.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Seed from registry'}
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleSeed(true)} disabled={seedCosts.isPending}>
              Refresh estimates
            </Button>
            <Button variant="outline" size="sm" onClick={() => setRegistryPricingOpen(true)}>
              Seed missing pricing
              {(registryGaps?.gap_count ?? 0) > 0 ? ` (${registryGaps?.gap_count})` : ''}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setGenerateOpen(true)}>
              <Sparkles className="mr-1 h-4 w-4" />
              Auto-generate (routing)
            </Button>
            <Button size="sm" onClick={openCreate}>
              <Plus className="mr-1 h-4 w-4" />
              Add cost
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div>
              <p className="text-sm text-destructive">Failed to load model costs.</p>
              <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          ) : (
            <>
              <div className="flex gap-1 mb-4 flex-wrap">
                <Button
                  variant={providerFilter === 'all' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setProviderFilter('all');
                    setModelFilter('all');
                  }}
                >
                  All
                </Button>
                {providerTabs.map((provider) => (
                  <Button
                    key={provider}
                    variant={providerFilter === provider ? 'default' : 'outline'}
                    size="sm"
                    className="capitalize"
                    onClick={() => {
                      setProviderFilter(provider);
                      setModelFilter('all');
                    }}
                  >
                    {provider}
                  </Button>
                ))}
              </div>

              {modelOptions.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 mb-4">
                  <Label className="text-xs text-muted-foreground shrink-0">Filter model</Label>
                  <Select
                    value={modelFilter}
                    onValueChange={setModelFilter}
                  >
                    <SelectTrigger className="w-64">
                      <SelectValue placeholder="All models" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All models</SelectItem>
                      {modelOptions.map((model) => (
                        <SelectItem key={model || '__default__'} value={model}>
                          {model || '(provider default)'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Provider</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Operation</TableHead>
                    <TableHead>Cost (USD)</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead className="w-[90px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredCosts.length > 0 ? (
                    filteredCosts.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium capitalize">{item.ai_service}</TableCell>
                        <TableCell className="font-mono text-sm">
                          {item.sub_model || <span className="text-muted-foreground italic">default</span>}
                        </TableCell>
                        <TableCell>
                          {OPERATION_TYPES.find((op) => op.value === item.operation_type)?.label
                            ?? item.operation_type}
                        </TableCell>
                        <TableCell>{formatUsd(item.cost_usd)}</TableCell>
                        <TableCell className="text-muted-foreground text-xs">{item.source}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="sm" onClick={() => openEdit(item)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(item)}>
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        {costs && costs.length > 0
                          ? 'No rows match the current filters.'
                          : 'No model costs yet. Seed from registry or add manually.'}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit model cost' : 'Add model cost'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label>AI Service</Label>
              <Input {...form.register('ai_service')} disabled={!!editing} />
            </div>
            <div className="space-y-2">
              <Label>Operation</Label>
              <Select
                value={form.watch('operation_type')}
                onValueChange={(val) => form.setValue('operation_type', val)}
                disabled={!!editing}
              >
                <SelectTrigger><SelectValue placeholder="Select operation" /></SelectTrigger>
                <SelectContent>
                  {OPERATION_TYPES.map((op) => (
                    <SelectItem key={op.value} value={op.value}>{op.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Model id</Label>
              <Input
                {...form.register('sub_model')}
                placeholder="e.g. deepseek-chat (leave empty for provider default)"
                disabled={!!editing}
              />
            </div>
            <div className="space-y-2">
              <Label>Cost (USD)</Label>
              <Input type="number" step="0.0001" min={0} {...form.register('cost_usd', { valueAsNumber: true })} />
              <p className="text-xs text-muted-foreground">
                Fractional USD supported (e.g. 0.0003 for DeepSeek text calls).
              </p>
            </div>
            <div className="space-y-2">
              <Label>Notes</Label>
              <Input {...form.register('notes')} />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={createCost.isPending || updateCost.isPending}>
                {(createCost.isPending || updateCost.isPending) && (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                )}
                Save
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={registryPricingOpen} onOpenChange={setRegistryPricingOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Seed missing pricing from registry</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Compares the model registry catalog to your credit pricing table. Only
              <strong className="text-slate-300"> missing </strong>
              rows are created, always marked
              <strong className="text-slate-300"> needs review</strong>. Existing
              pricing is never changed.
            </p>
            {(registryGaps?.gap_count ?? 0) > 0 ? (
              <div className="rounded-md border border-amber-800/60 bg-amber-950/20 p-3 text-sm">
                <p className="font-medium text-amber-200">
                  {registryGaps?.gap_count} registry pair(s) not priced yet
                </p>
                <p className="mt-1 text-muted-foreground text-xs">
                  e.g. new models like gpt-5.6-luna after registry seed
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No registry gaps — pricing already covers the catalog.
              </p>
            )}
            <div className="space-y-2">
              <Label>Target profit margin (% of revenue)</Label>
              <Input
                type="number"
                min={0}
                max={99}
                step={0.5}
                value={marginPercent}
                onChange={(e) => setMarginPercent(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              onClick={handleSeedRegistryPricing}
              disabled={seedRegistryPricing.isPending || !(registryGaps?.gap_count ?? 0)}
            >
              {seedRegistryPricing.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              Create draft pricing
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={generateOpen} onOpenChange={setGenerateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Auto-generate pricing (routing)</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Creates draft pricing for provider/model/operation pairs required by
              <strong className="text-slate-300"> AI routing</strong> (primary +
              fallback chains). Use
              <strong className="text-slate-300"> Seed missing pricing</strong> for
              the full registry catalog instead.
            </p>
            <div className="rounded-md border border-slate-700 bg-slate-900/40 p-3 text-sm text-slate-300">
              <p className="font-medium text-slate-200">What happens to existing pricing?</p>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-muted-foreground">
                <li>
                  <strong className="text-slate-300">By default:</strong> existing rows are left unchanged.
                  Only missing rows are created (marked needs review).
                </li>
                <li>
                  <strong className="text-slate-300">With overwrite checked:</strong> matching rows are
                  recalculated from current model costs and your margin.
                </li>
              </ul>
            </div>
            <div className="space-y-2">
              <Label>Target profit margin (% of revenue)</Label>
              <Input
                type="number"
                min={0}
                max={99}
                step={0.5}
                value={marginPercent}
                onChange={(e) => setMarginPercent(e.target.value)}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={overwriteExisting}
                onChange={(e) => setOverwriteExisting(e.target.checked)}
              />
              Overwrite existing pricing rows
            </label>
          </div>
          <DialogFooter>
            <Button onClick={handleGenerate} disabled={generatePricing.isPending}>
              {generatePricing.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              Generate draft pricing
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Delete model cost?</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">
            {deleteTarget?.ai_service} / {deleteTarget?.sub_model || 'default'} / {deleteTarget?.operation_type}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteCost.isPending}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
