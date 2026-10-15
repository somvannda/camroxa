import { useCallback, useMemo, useState } from 'react';
import { AxiosError } from 'axios';
import { Loader2, Music2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { ErrorState } from '@/components/shared/error-state';
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useCreateWebMusicPlan,
  useCreateWebMusicTopup,
  useDeleteWebMusicPlan,
  useDeleteWebMusicTopup,
  useUpdateWebMusicPlan,
  useUpdateWebMusicTopup,
  useWebMusicPlans,
  useWebMusicTopups,
} from '@/hooks/use-web-music-plans';
import { formatUsd } from '@/lib/plan-tier-pricing';
import { toast } from '@/hooks/use-toast';
import type { WebMusicPlan, WebMusicTopupPack } from '@/types/models';

const planSchema = z.object({
  name: z.string().min(1, 'Name is required').max(50),
  price_cents: z.number().min(0),
  billing_cycle_days: z.number().min(1),
  monthly_credits: z.number().min(1).max(1_000_000),
  display_order: z.number().min(0).max(100),
  is_public: z.boolean(),
  feature_music: z.boolean(),
  feature_images: z.boolean(),
  feature_topup: z.boolean(),
});

type PlanFormValues = z.infer<typeof planSchema>;

const topupSchema = z.object({
  slug: z.string().min(2).max(50).regex(/^[a-z0-9][a-z0-9_-]*[a-z0-9]$|^[a-z0-9]$/, 'Lowercase slug only'),
  name: z.string().min(1).max(100),
  total_credits: z.number().min(10).max(1_000_000),
  price_cents: z.number().min(0),
  display_order: z.number().min(0).max(100),
  is_active: z.boolean(),
});

type TopupFormValues = z.infer<typeof topupSchema>;

function billingLabel(days: number): string {
  if (days === 365) return 'Yearly';
  if (days === 180) return '6 Months';
  return 'Monthly';
}

function tierLabel(plan: WebMusicPlan): string {
  const base = plan.name.split('_')[0] ?? plan.name;
  return base.charAt(0).toUpperCase() + base.slice(1);
}

function groupPlans(plans: WebMusicPlan[]) {
  const groups = new Map<number, WebMusicPlan[]>();
  for (const plan of plans) {
    const key = plan.display_order;
    const list = groups.get(key) ?? [];
    list.push(plan);
    groups.set(key, list);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a - b)
    .flatMap(([displayOrder, rows]) => {
      const first = rows[0];
      if (!first) return [];
      return [
        {
          displayOrder,
          label: tierLabel(first),
          monthly: rows.find((row) => row.billing_cycle_days === 30),
          yearly: rows.find((row) => row.billing_cycle_days === 365),
        },
      ];
    });
}

function apiError(err: unknown, fallback: string): string {
  const axiosError = err as AxiosError<{ detail?: string; error?: { message?: string } }>;
  return (
    axiosError.response?.data?.error?.message ??
    axiosError.response?.data?.detail ??
    fallback
  );
}

/**
 * Subscriptions are retired on music.camxora.com; credit packs are the only
 * product. Flip this to true to bring the subscription-plan editor back (e.g. a
 * migration, or adjusting a grandfathered term). Left false it hides plan
 * management while keeping the code and its handlers intact and build-clean.
 */
const MANAGE_SUBSCRIPTION_PLANS = false;

export function WebMusicPlansSection() {
  const { data: plans, isLoading, isError, error, refetch } = useWebMusicPlans();
  const { data: topups, isLoading: topupsLoading, isError: topupsError, error: topupsErr, refetch: refetchTopups } =
    useWebMusicTopups();

  const createPlan = useCreateWebMusicPlan();
  const updatePlan = useUpdateWebMusicPlan();
  const deletePlan = useDeleteWebMusicPlan();
  const createTopup = useCreateWebMusicTopup();
  const updateTopup = useUpdateWebMusicTopup();
  const deleteTopup = useDeleteWebMusicTopup();

  const [planDialogOpen, setPlanDialogOpen] = useState(false);
  const [topupDialogOpen, setTopupDialogOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<WebMusicPlan | null>(null);
  const [editingTopup, setEditingTopup] = useState<WebMusicTopupPack | null>(null);
  const [deletePlanTarget, setDeletePlanTarget] = useState<WebMusicPlan | null>(null);
  const [deleteTopupTarget, setDeleteTopupTarget] = useState<WebMusicTopupPack | null>(null);

  const planForm = useForm<PlanFormValues>({
    resolver: zodResolver(planSchema),
    defaultValues: {
      name: '',
      price_cents: 1000,
      billing_cycle_days: 30,
      monthly_credits: 1000,
      display_order: 1,
      is_public: true,
      feature_music: true,
      feature_images: false,
      feature_topup: true,
    },
  });

  const topupForm = useForm<TopupFormValues>({
    resolver: zodResolver(topupSchema),
    defaultValues: {
      slug: '',
      name: '',
      total_credits: 400,
      price_cents: 500,
      display_order: 1,
      is_active: true,
    },
  });

  const groupedPlans = useMemo(() => groupPlans(plans ?? []), [plans]);

  const openCreatePlan = useCallback(() => {
    setEditingPlan(null);
    planForm.reset({
      name: '',
      price_cents: 1000,
      billing_cycle_days: 30,
      monthly_credits: 1000,
      display_order: (plans?.length ?? 0) + 1,
      is_public: true,
      feature_music: true,
      feature_images: false,
      feature_topup: true,
    });
    setPlanDialogOpen(true);
  }, [planForm, plans?.length]);

  const openEditPlan = useCallback(
    (plan: WebMusicPlan) => {
      setEditingPlan(plan);
      planForm.reset({
        name: plan.name,
        price_cents: plan.price_cents,
        billing_cycle_days: plan.billing_cycle_days,
        monthly_credits: plan.monthly_credits,
        display_order: plan.display_order,
        is_public: plan.is_public,
        feature_music: plan.features.music,
        feature_images: plan.features.images,
        feature_topup: plan.features.topup,
      });
      setPlanDialogOpen(true);
    },
    [planForm],
  );

  const openCreateTopup = useCallback(() => {
    setEditingTopup(null);
    topupForm.reset({
      slug: '',
      name: '',
      total_credits: 400,
      price_cents: 500,
      display_order: (topups?.length ?? 0) + 1,
      is_active: true,
    });
    setTopupDialogOpen(true);
  }, [topupForm, topups?.length]);

  const openEditTopup = useCallback(
    (pack: WebMusicTopupPack) => {
      setEditingTopup(pack);
      topupForm.reset({
        slug: pack.slug,
        name: pack.name,
        total_credits: pack.total_credits,
        price_cents: pack.price_cents,
        display_order: pack.display_order,
        is_active: pack.is_active,
      });
      setTopupDialogOpen(true);
    },
    [topupForm],
  );

  const submitPlan = (values: PlanFormValues) => {
    const payload = {
      name: values.name,
      price_cents: values.price_cents,
      billing_cycle_days: values.billing_cycle_days,
      monthly_credits: values.monthly_credits,
      display_order: values.display_order,
      is_public: values.is_public,
      features: {
        music: values.feature_music,
        images: values.feature_images,
        topup: values.feature_topup,
      },
    };

    if (editingPlan) {
      updatePlan.mutate(
        { id: editingPlan.id, updates: payload },
        {
          onSuccess: () => {
            toast({ title: 'Web music plan updated' });
            setPlanDialogOpen(false);
            setEditingPlan(null);
          },
          onError: (err) => toast({ title: 'Error', description: apiError(err, 'Failed to update plan'), variant: 'destructive' }),
        },
      );
      return;
    }

    createPlan.mutate(payload, {
      onSuccess: () => {
        toast({ title: 'Web music plan created' });
        setPlanDialogOpen(false);
      },
      onError: (err) => toast({ title: 'Error', description: apiError(err, 'Failed to create plan'), variant: 'destructive' }),
    });
  };

  const submitTopup = (values: TopupFormValues) => {
    const payload = {
      slug: values.slug,
      name: values.name,
      total_credits: values.total_credits,
      price_cents: values.price_cents,
      display_order: values.display_order,
      is_active: values.is_active,
    };

    if (editingTopup) {
      updateTopup.mutate(
        { id: editingTopup.id, updates: payload },
        {
          onSuccess: () => {
            toast({ title: 'Top-up pack updated' });
            setTopupDialogOpen(false);
            setEditingTopup(null);
          },
          onError: (err) => toast({ title: 'Error', description: apiError(err, 'Failed to update pack'), variant: 'destructive' }),
        },
      );
      return;
    }

    createTopup.mutate(payload, {
      onSuccess: () => {
        toast({ title: 'Top-up pack created' });
        setTopupDialogOpen(false);
      },
      onError: (err) => toast({ title: 'Error', description: apiError(err, 'Failed to create pack'), variant: 'destructive' }),
    });
  };

  const handleTogglePlanActive = (plan: WebMusicPlan) => {
    updatePlan.mutate(
      { id: plan.id, updates: { is_active: !plan.is_active } },
      {
        onSuccess: () => toast({ title: plan.is_active ? 'Plan deactivated' : 'Plan activated' }),
      },
    );
  };

  const handleToggleTopupActive = (pack: WebMusicTopupPack) => {
    updateTopup.mutate(
      { id: pack.id, updates: { is_active: !pack.is_active } },
      {
        onSuccess: () => toast({ title: pack.is_active ? 'Pack deactivated' : 'Pack activated' }),
      },
    );
  };

  return (
    <>
      {MANAGE_SUBSCRIPTION_PLANS ? (
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Music2 className="h-5 w-5 text-violet-400" />
              Web Music Plans
            </CardTitle>
            <CardDescription className="mt-1 max-w-2xl">
              Manage music.camxora.com subscription tiers separately from desktop channel plans.
              Credits renew each billing period; 10 credits = 1 generate = 2 songs.
            </CardDescription>
          </div>
          <Button size="sm" onClick={openCreatePlan}>
            Create Plan
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : isError ? (
            <ErrorState message={error?.message ?? 'Failed to load web music plans'} onRetry={() => refetch()} />
          ) : groupedPlans.length === 0 ? (
            <p className="py-4 text-center text-slate-400">No web music plans yet.</p>
          ) : (
            <div className="space-y-4">
              {groupedPlans.map((group) => (
                <div key={group.displayOrder} className="rounded-lg border border-violet-500/20 bg-violet-500/5 p-4">
                  <div className="mb-3 text-sm font-medium text-violet-200">{group.label}</div>
                  <div className="grid gap-3 md:grid-cols-2">
                    {[group.monthly, group.yearly].map((plan) =>
                      plan ? (
                        <PlanRow
                          key={plan.id}
                          plan={plan}
                          onEdit={openEditPlan}
                          onToggleActive={handleTogglePlanActive}
                          onDelete={setDeletePlanTarget}
                        />
                      ) : (
                        <div
                          key={`missing-${group.displayOrder}`}
                          className="rounded-lg border border-dashed border-slate-700 px-4 py-3 text-sm text-slate-500"
                        >
                          Missing billing term row
                        </div>
                      ),
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Music2 className="h-5 w-5 text-violet-400" />
              Web Music Plans (retired)
            </CardTitle>
            <CardDescription className="mt-1 max-w-2xl">
              Subscriptions are no longer sold on music.camxora.com — credit packs are the only
              product. Existing plan rows only matter to grandfathered subscribers, who keep the
              term they already paid for. Manage pack pricing in the section below.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="text-lg">Web Music Top-Up Packs</CardTitle>
            <CardDescription>One-time credit packs shown in the music web top-up modal.</CardDescription>
          </div>
          <Button size="sm" onClick={openCreateTopup}>
            Create Pack
          </Button>
        </CardHeader>
        <CardContent>
          {topupsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : topupsError ? (
            <ErrorState message={topupsErr?.message ?? 'Failed to load top-up packs'} onRetry={() => refetchTopups()} />
          ) : topups?.length === 0 ? (
            <p className="py-4 text-center text-slate-400">No top-up packs yet.</p>
          ) : (
            <div className="space-y-3">
              {topups?.map((pack) => (
                <div
                  key={pack.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3"
                >
                  <div>
                    <div className="text-sm font-medium text-white">{pack.name}</div>
                    <div className="text-xs text-slate-400">
                      {pack.slug} · {pack.total_credits.toLocaleString()} credits · ~{pack.songs_equivalent} songs ·{' '}
                      {formatUsd(pack.price_cents)}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline" className={pack.is_active ? 'border-green-500/30 text-green-400' : 'border-slate-600 text-slate-400'}>
                      {pack.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                    <Button size="sm" variant="outline" onClick={() => openEditTopup(pack)}>
                      Edit
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleToggleTopupActive(pack)}>
                      {pack.is_active ? 'Deactivate' : 'Activate'}
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => setDeleteTopupTarget(pack)}>
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={planDialogOpen} onOpenChange={setPlanDialogOpen}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingPlan ? 'Edit Web Music Plan' : 'Create Web Music Plan'}</DialogTitle>
            <DialogDescription>
              Plans with the same display order are grouped as one tier on the pricing modal.
            </DialogDescription>
          </DialogHeader>
          <Form {...planForm}>
            <form onSubmit={planForm.handleSubmit(submitPlan)} className="space-y-4">
              <FormField
                control={planForm.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Internal name</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="starter_monthly" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={planForm.control}
                  name="price_cents"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Price (cents)</FormLabel>
                      <FormControl>
                        <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={planForm.control}
                  name="billing_cycle_days"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Billing cycle (days)</FormLabel>
                      <div className="flex flex-wrap gap-2">
                        <FormControl>
                          <Input type="number" className="max-w-[120px]" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                        </FormControl>
                        {[30, 365].map((days) => (
                          <Button key={days} type="button" size="sm" variant="outline" onClick={() => field.onChange(days)}>
                            {billingLabel(days)}
                          </Button>
                        ))}
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={planForm.control}
                  name="monthly_credits"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Monthly credits</FormLabel>
                      <FormControl>
                        <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={planForm.control}
                  name="display_order"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Tier order</FormLabel>
                      <FormControl>
                        <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={planForm.control}
                name="is_public"
                render={({ field }) => (
                  <FormItem className="flex items-center justify-between rounded-lg border border-slate-800 px-3 py-2">
                    <FormLabel>Show on public pricing page</FormLabel>
                    <FormControl>
                      <input
                        type="checkbox"
                        checked={field.value}
                        onChange={(event) => field.onChange(event.target.checked)}
                        className="h-4 w-4 rounded border-slate-600"
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
              <div className="space-y-2 rounded-lg border border-slate-800 p-3">
                <div className="text-sm font-medium text-slate-200">Features</div>
                {(['feature_music', 'feature_images', 'feature_topup'] as const).map((name) => (
                  <FormField
                    key={name}
                    control={planForm.control}
                    name={name}
                    render={({ field }) => (
                      <FormItem className="flex items-center justify-between">
                        <FormLabel className="capitalize">{name.replace('feature_', '')}</FormLabel>
                        <FormControl>
                          <input
                            type="checkbox"
                            checked={field.value}
                            onChange={(event) => field.onChange(event.target.checked)}
                            className="h-4 w-4 rounded border-slate-600"
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                ))}
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setPlanDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createPlan.isPending || updatePlan.isPending}>
                  {(createPlan.isPending || updatePlan.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingPlan ? 'Save Changes' : 'Create Plan'}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Dialog open={topupDialogOpen} onOpenChange={setTopupDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingTopup ? 'Edit Top-Up Pack' : 'Create Top-Up Pack'}</DialogTitle>
          </DialogHeader>
          <Form {...topupForm}>
            <form onSubmit={topupForm.handleSubmit(submitTopup)} className="space-y-4">
              <FormField
                control={topupForm.control}
                name="slug"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Slug</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="medium" disabled={!!editingTopup} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={topupForm.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Display name</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="Medium Pack" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={topupForm.control}
                  name="total_credits"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Credits</FormLabel>
                      <FormControl>
                        <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={topupForm.control}
                  name="price_cents"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Price (cents)</FormLabel>
                      <FormControl>
                        <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={topupForm.control}
                  name="display_order"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Display order</FormLabel>
                      <FormControl>
                        <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={topupForm.control}
                  name="is_active"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between rounded-lg border border-slate-800 px-3 py-2">
                      <FormLabel>Active</FormLabel>
                      <FormControl>
                        <input
                          type="checkbox"
                          checked={field.value}
                          onChange={(event) => field.onChange(event.target.checked)}
                          className="h-4 w-4 rounded border-slate-600"
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setTopupDialogOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createTopup.isPending || updateTopup.isPending}>
                  {(createTopup.isPending || updateTopup.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingTopup ? 'Save Changes' : 'Create Pack'}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deletePlanTarget}
        onOpenChange={(open) => {
          if (!open) setDeletePlanTarget(null);
        }}
        title="Delete web music plan?"
        description={
          deletePlanTarget
            ? `Permanently delete "${deletePlanTarget.name}"? This cannot be undone.`
            : ''
        }
        onConfirm={() => {
          if (!deletePlanTarget) return;
          deletePlan.mutate(deletePlanTarget.id, {
            onSuccess: () => {
              toast({ title: 'Plan deleted' });
              setDeletePlanTarget(null);
            },
            onError: (err) =>
              toast({ title: 'Error', description: apiError(err, 'Failed to delete plan'), variant: 'destructive' }),
          });
        }}
        variant="destructive"
        confirmText="Delete"
        isLoading={deletePlan.isPending}
      />

      <ConfirmDialog
        open={!!deleteTopupTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTopupTarget(null);
        }}
        title="Delete top-up pack?"
        description={
          deleteTopupTarget ? `Permanently delete "${deleteTopupTarget.name}"? This cannot be undone.` : ''
        }
        onConfirm={() => {
          if (!deleteTopupTarget) return;
          deleteTopup.mutate(deleteTopupTarget.id, {
            onSuccess: () => {
              toast({ title: 'Pack deleted' });
              setDeleteTopupTarget(null);
            },
            onError: (err) =>
              toast({ title: 'Error', description: apiError(err, 'Failed to delete pack'), variant: 'destructive' }),
          });
        }}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteTopup.isPending}
      />
    </>
  );
}

function PlanRow({
  plan,
  onEdit,
  onToggleActive,
  onDelete,
}: {
  plan: WebMusicPlan;
  onEdit: (plan: WebMusicPlan) => void;
  onToggleActive: (plan: WebMusicPlan) => void;
  onDelete: (plan: WebMusicPlan) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3">
      <div>
        <div className="text-sm font-medium text-white">{billingLabel(plan.billing_cycle_days)}</div>
        <div className="text-xs text-slate-400">
          {plan.name} · {formatUsd(plan.price_cents)} · {plan.monthly_credits.toLocaleString()} credits/mo
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          {plan.is_public ? (
            <Badge variant="outline" className="border-violet-500/30 text-violet-300">
              Public
            </Badge>
          ) : null}
          {plan.subscriber_count > 0 ? (
            <Badge variant="outline" className="border-slate-600 text-slate-300">
              {plan.subscriber_count} subs
            </Badge>
          ) : null}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className={plan.is_active ? 'border-green-500/30 text-green-400' : 'border-slate-600 text-slate-400'}>
          {plan.is_active ? 'Active' : 'Inactive'}
        </Badge>
        <Button size="sm" variant="outline" onClick={() => onEdit(plan)}>
          Edit
        </Button>
        <Button size="sm" variant="outline" onClick={() => onToggleActive(plan)}>
          {plan.is_active ? 'Deactivate' : 'Activate'}
        </Button>
        <Button size="sm" variant="destructive" disabled={!plan.can_delete} onClick={() => onDelete(plan)}>
          Delete
        </Button>
      </div>
    </div>
  );
}
