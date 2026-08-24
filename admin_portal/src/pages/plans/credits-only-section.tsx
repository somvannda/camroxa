import { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { AxiosError } from 'axios';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ErrorState } from '@/components/shared/error-state';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useCreatePlan } from '@/hooks/use-plans';
import { usePatchV3Plan, useV3Plans } from '@/hooks/use-v3-plans';
import { toast } from '@/hooks/use-toast';
import { formatUsd } from '@/lib/plan-tier-pricing';
import {
  CreditsOnlyPlanFields,
  emptyCreditsOnlyForm,
  formFromCredits,
  parseOptionalCredits,
  type CreditsOnlyFormValues,
} from '@/pages/plans/credits-only-plan-fields';
import { V3_PLAN_OPS, type V3Plan, type V3PlanPatch } from '@/types/v3-billing';

function buildPatch(values: CreditsOnlyFormValues): V3PlanPatch | null {
  const monthly = Number.parseInt(values.monthly_credits, 10);
  const daily = Number.parseInt(values.daily_credits, 10);
  if (!Number.isInteger(monthly) || monthly < 0 || !Number.isInteger(daily) || daily < 0) {
    return null;
  }
  const patch: V3PlanPatch = {
    monthly_credits: monthly,
    daily_credits: daily,
    is_public: values.is_public,
    is_active: values.is_active,
  };
  for (const op of V3_PLAN_OPS) {
    const parsed = parseOptionalCredits(values.ops[op]);
    if (Number.isNaN(parsed)) return null;
    patch[`${op}_credits`] = parsed;
  }
  return patch;
}

const LEGACY_CREATE_DEFAULTS = {
  monthly_song_limit: 0,
  monthly_image_limit: 0,
  monthly_draft_limit: 0,
  monthly_video_limit: 0,
  monthly_merge_limit: 0,
  daily_song_limit_per_channel: 1,
  daily_image_limit_per_channel: 1,
  daily_draft_limit_per_channel: 1,
  daily_video_limit: 1,
  daily_merge_limit: 1,
  plan_kind: 'subscription' as const,
};

function formatBilling(days: number | null): string {
  if (!days) return '—';
  if (days === 30) return 'Monthly';
  if (days === 180) return '6 months';
  if (days === 365 || days === 366) return 'Yearly';
  return `${days}d`;
}

function formatGrant(plan: V3Plan): string {
  if (plan.monthly_credits <= 0 && plan.daily_credits > 0) {
    return `${plan.daily_credits.toLocaleString()} / day`;
  }
  if (plan.daily_credits > 0) {
    return `${plan.monthly_credits.toLocaleString()} / period + ${plan.daily_credits.toLocaleString()} / day`;
  }
  return `${plan.monthly_credits.toLocaleString()} / period`;
}

function formatApproxSongs(plan: V3Plan): string {
  if (plan.monthly_credits > 0) {
    return String(Math.floor(plan.monthly_credits / 10));
  }
  if (plan.daily_credits > 0) {
    return `${Math.floor(plan.daily_credits / 10)}/day`;
  }
  return '—';
}

function formatOpAmount(value: number | null): string {
  if (value == null) return '—';
  return String(value);
}

const OP_COLUMNS: Array<{ id: keyof V3Plan; label: string }> = [
  { id: 'lyric_credits', label: 'Lyric' },
  { id: 'title_credits', label: 'Title' },
  { id: 'album_credits', label: 'Album' },
  { id: 'music_credits', label: 'Music' },
  { id: 'style_credits', label: 'Style' },
  { id: 'image_credits', label: 'Image' },
  { id: 'video_credits', label: 'Video' },
  { id: 'merge_credits', label: 'Merge' },
];

const TABLE_COL_COUNT = 7 + OP_COLUMNS.length;

function isProfileAddon(plan: V3Plan): boolean {
  return (plan.plan_kind ?? '').toLowerCase() === 'profile_addon' || /^add-on/i.test(plan.name);
}

function sortCatalog(plans: V3Plan[]): V3Plan[] {
  return [...plans].sort((a, b) => {
    if (a.is_public !== b.is_public) return a.is_public ? -1 : 1;
    if (a.price_cents !== b.price_cents) return a.price_cents - b.price_cents;
    return a.name.localeCompare(b.name);
  });
}

function VisibilityBadge({ plan }: { plan: V3Plan }) {
  return (
    <Badge
      variant="outline"
      className={
        plan.is_public
          ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300'
          : 'border-slate-600 text-slate-400'
      }
    >
      {plan.is_public ? 'Public' : 'Hidden'}
    </Badge>
  );
}

function PlansTable({
  plans,
  onEdit,
  emptyMessage,
}: {
  plans: V3Plan[];
  onEdit: (plan: V3Plan) => void;
  emptyMessage: string;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>Plan</TableHead>
          <TableHead>Price</TableHead>
          <TableHead>Billing</TableHead>
          <TableHead className="text-right">Grant</TableHead>
          <TableHead className="text-right" title="Display only. floor(grant / 10). Not a quota.">
            ≈ Songs
          </TableHead>
          {OP_COLUMNS.map((column) => (
            <TableHead key={column.id} className="text-right">
              {column.label}
            </TableHead>
          ))}
          <TableHead>Visibility</TableHead>
          <TableHead className="text-right"> </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {plans.length === 0 ? (
          <TableRow>
            <TableCell colSpan={TABLE_COL_COUNT} className="py-10 text-center text-slate-500">
              {emptyMessage}
            </TableCell>
          </TableRow>
        ) : (
          plans.map((plan) => (
            <TableRow key={plan.id}>
              <TableCell>
                <div className="font-medium text-slate-100">{plan.name}</div>
                {plan.profile_allowance > 0 ? (
                  <div className="text-xs text-slate-500">
                    {plan.profile_allowance} profiles
                  </div>
                ) : null}
              </TableCell>
              <TableCell className="tabular-nums text-slate-200">
                {formatUsd(plan.price_cents)}
              </TableCell>
              <TableCell className="text-slate-300">{formatBilling(plan.billing_cycle_days)}</TableCell>
              <TableCell className="text-right tabular-nums text-slate-200">
                {formatGrant(plan)}
              </TableCell>
              <TableCell className="text-right tabular-nums text-slate-500">
                {formatApproxSongs(plan)}
              </TableCell>
              {OP_COLUMNS.map((column) => (
                <TableCell
                  key={column.id}
                  className="text-right tabular-nums text-slate-300"
                >
                  {formatOpAmount(plan[column.id] as number | null)}
                </TableCell>
              ))}
              <TableCell>
                <VisibilityBadge plan={plan} />
              </TableCell>
              <TableCell className="text-right">
                <Button size="sm" variant="outline" onClick={() => onEdit(plan)}>
                  Edit
                </Button>
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}

export function CreditsOnlySection() {
  const { data: plans, isLoading, isError, error, refetch } = useV3Plans();
  const patchPlan = usePatchV3Plan();
  const createPlan = useCreatePlan();
  const [selected, setSelected] = useState<V3Plan | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [showLeftovers, setShowLeftovers] = useState(false);
  const [showAddons, setShowAddons] = useState(false);
  const [form, setForm] = useState<CreditsOnlyFormValues>(emptyCreditsOnlyForm());
  const [createName, setCreateName] = useState('');
  const [createPriceCents, setCreatePriceCents] = useState('0');
  const [createBillingDays, setCreateBillingDays] = useState('30');
  const [createProfileAllowance, setCreateProfileAllowance] = useState('2');

  useEffect(() => {
    if (!selected) return;
    setForm(formFromCredits(selected));
  }, [selected]);

  const openCreate = () => {
    setCreateName('');
    setCreatePriceCents('0');
    setCreateBillingDays('30');
    setCreateProfileAllowance('2');
    setForm(emptyCreditsOnlyForm());
    setCreateOpen(true);
  };

  const handleCreate = () => {
    const updates = buildPatch(form);
    const price = Number.parseInt(createPriceCents, 10);
    const days = Number.parseInt(createBillingDays, 10);
    const profiles = Number.parseInt(createProfileAllowance, 10);
    if (!createName.trim()) {
      toast({ title: 'Name is required', variant: 'destructive' });
      return;
    }
    if (!Number.isInteger(price) || price < 0 || !Number.isInteger(days) || days < 1 || !Number.isInteger(profiles) || profiles < 1) {
      toast({
        title: 'Invalid plan identity',
        description: 'Price must be >= 0 cents. Billing days and profile allowance must be whole numbers >= 1.',
        variant: 'destructive',
      });
      return;
    }
    if (updates == null) {
      toast({
        title: 'Invalid credits',
        description: 'Grants and per-op amounts must be empty (fallback) or whole numbers >= 0.',
        variant: 'destructive',
      });
      return;
    }
    createPlan.mutate(
      {
        name: createName.trim(),
        price_cents: price,
        profile_allowance: profiles,
        billing_cycle_days: days,
        ...LEGACY_CREATE_DEFAULTS,
      },
      {
        onSuccess: (created) => {
          patchPlan.mutate(
            { id: created.id, updates },
            {
              onSuccess: () => {
                toast({ title: 'Credits-only plan created' });
                setCreateOpen(false);
              },
              onError: (err) => {
                const axiosError = err as AxiosError<{ detail?: string; error?: { message?: string } }>;
                toast({
                  title: 'Plan row created, credits patch failed',
                  description:
                    axiosError.response?.data?.error?.message ??
                    axiosError.response?.data?.detail ??
                    'v3 plan patch failed',
                  variant: 'destructive',
                });
              },
            },
          );
        },
        onError: (err) => {
          const axiosError = err as AxiosError<{ detail?: string }>;
          toast({
            title: 'Could not create plan',
            description: axiosError.response?.data?.detail ?? 'v1 plan create failed',
            variant: 'destructive',
          });
        },
      },
    );
  };

  const handleSave = () => {
    if (!selected) return;
    const updates = buildPatch(form);
    if (updates == null) {
      toast({
        title: 'Invalid credits',
        description: 'Grants and per-op amounts must be empty (fallback) or whole numbers ≥ 0.',
        variant: 'destructive',
      });
      return;
    }
    patchPlan.mutate(
      { id: selected.id, updates },
      {
        onSuccess: () => {
          toast({ title: 'Credits-only plan saved' });
          setSelected(null);
        },
        onError: (err) => {
          const axiosError = err as AxiosError<{ detail?: string; error?: { message?: string } }>;
          toast({
            title: 'Could not save credits',
            description:
              axiosError.response?.data?.error?.message ??
              axiosError.response?.data?.detail ??
              'v3 plan patch failed',
            variant: 'destructive',
          });
        },
      },
    );
  };

  const catalog = useMemo(() => {
    const rows = plans ?? [];
    const addons = rows.filter((plan) => isProfileAddon(plan));
    const creditRows = rows.filter((plan) => !isProfileAddon(plan));
    return {
      live: sortCatalog(creditRows.filter((plan) => plan.is_active)),
      leftover: sortCatalog(creditRows.filter((plan) => !plan.is_active)),
      addons: sortCatalog(addons),
    };
  }, [plans]);

  return (
    <>
      <Card className="border-violet-500/20 bg-slate-900/50">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="text-lg text-slate-100">Credits-only catalog</CardTitle>
              <CardDescription className="mt-1.5">
                Live rows only. ≈ Songs is display-only: floor(grant / 10). It is not a quota.
                Per-op 0 = included. Empty (—) falls back to the Credits page. Extra profiles do
                not multiply credits.
              </CardDescription>
            </div>
            <Button size="sm" onClick={openCreate}>
              Create plan
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {isLoading ? (
            <div className="flex items-center gap-2 py-6 text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading credits-only plan fields…
            </div>
          ) : isError ? (
            <ErrorState
              message={error instanceof Error ? error.message : 'Failed to load v3 plans'}
              onRetry={() => refetch()}
            />
          ) : !plans?.length ? (
            <p className="text-sm text-slate-400">No plan rows yet.</p>
          ) : (
            <>
              <PlansTable
                plans={catalog.live}
                onEdit={setSelected}
                emptyMessage="No active credit plans."
              />
              {catalog.addons.length > 0 ? (
                <div className="space-y-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-auto px-0 text-slate-500 hover:text-slate-300"
                    onClick={() => setShowAddons((open) => !open)}
                  >
                    {showAddons ? 'Hide' : 'Show'} profile add-ons ({catalog.addons.length})
                  </Button>
                  {showAddons ? (
                    <div className="space-y-2">
                      <p className="text-xs text-slate-500">
                        Extra profile slots only. They do not grant credits. Generate still uses
                        the user&apos;s credit plan (music = 10). These rows now store the same
                        per-op amounts so they do not fall back to the Credits page.
                      </p>
                      <PlansTable
                        plans={catalog.addons}
                        onEdit={setSelected}
                        emptyMessage="No profile add-ons."
                      />
                    </div>
                  ) : null}
                </div>
              ) : null}
              {catalog.leftover.length > 0 ? (
                <div className="space-y-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-auto px-0 text-slate-500 hover:text-slate-300"
                    onClick={() => setShowLeftovers((open) => !open)}
                  >
                    {showLeftovers ? 'Hide' : 'Show'} leftover channel SKUs ({catalog.leftover.length})
                  </Button>
                  {showLeftovers ? (
                    <div className="space-y-2">
                      <p className="text-xs text-slate-500">
                        Old 6-channel / 10-channel / term rows. Turned off so they cannot grant or
                        renew. Kept so old licenses still resolve a plan id. Not for sale.
                      </p>
                      <PlansTable
                        plans={catalog.leftover}
                        onEdit={setSelected}
                        emptyMessage="No leftover SKUs."
                      />
                    </div>
                  ) : null}
                </div>
              ) : null}
            </>
          )}
        </CardContent>

        <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
          <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Edit credits — {selected?.name}</DialogTitle>
              <DialogDescription>
                Hidden $79 stays on this same plan id. Extra profile slots stay on the license and do
                not multiply credits.
              </DialogDescription>
            </DialogHeader>
            <CreditsOnlyPlanFields values={form} onChange={setForm} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setSelected(null)}>
                Cancel
              </Button>
              <Button type="button" onClick={handleSave} disabled={patchPlan.isPending}>
                {patchPlan.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save credits
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </Card>

      <Dialog open={createOpen} onOpenChange={(open) => !open && setCreateOpen(false)}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create credits-only plan</DialogTitle>
            <DialogDescription>
              New rows stay hidden unless you mark them public. Free is $0 with daily credits.
              Hidden legacy rows stay active and unpublished.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="create-plan-name">Name</Label>
              <Input
                id="create-plan-name"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="create-plan-price">Price (cents)</Label>
              <Input
                id="create-plan-price"
                type="number"
                min={0}
                value={createPriceCents}
                onChange={(e) => setCreatePriceCents(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="create-plan-days">Billing cycle days</Label>
              <Input
                id="create-plan-days"
                type="number"
                min={1}
                value={createBillingDays}
                onChange={(e) => setCreateBillingDays(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="create-plan-profiles">Profile allowance</Label>
              <Input
                id="create-plan-profiles"
                type="number"
                min={1}
                value={createProfileAllowance}
                onChange={(e) => setCreateProfileAllowance(e.target.value)}
              />
              <p className="text-xs text-slate-500">
                License slot hint only. Extra profiles do not multiply credits.
              </p>
            </div>
          </div>
          <CreditsOnlyPlanFields values={form} onChange={setForm} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleCreate}
              disabled={createPlan.isPending || patchPlan.isPending}
            >
              {(createPlan.isPending || patchPlan.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create plan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
