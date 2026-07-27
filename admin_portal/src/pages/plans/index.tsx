import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { AxiosError } from 'axios';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { ErrorState } from '@/components/shared/error-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
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
import { usePlans, useCreatePlan, useUpdatePlan, useDeletePlan, useOffers, useCreateOffer, usePlanTermDiscounts } from '@/hooks/use-plans';
import { billingTermQuotes, formatChannelPlanName, formatUsd, linearPlanMonthlyCents } from '@/lib/plan-tier-pricing';
import { ChannelPricingSection } from '@/pages/plans/channel-pricing-section';
import { PlanLimitsFields } from '@/pages/plans/plan-limits-fields';
import { PlanPricingPreview, SmartPlanPriceCalculator } from '@/pages/plans/plan-pricing-preview';
import { SubscriptionPlansSection } from '@/pages/plans/subscription-plans-section';
import { toast } from '@/hooks/use-toast';
import type { Plan, PlanOffer } from '@/types/models';

// --- Zod Schemas ---

const planUpdateSchema = z.object({
  price_cents: z.number().min(0, 'Price must be 0 or greater'),
  profile_allowance: z.number().min(1, 'Profile allowance must be at least 1'),
  monthly_song_limit: z.number().int().min(0).max(100000).nullable(),
  monthly_image_limit: z.number().int().min(0).max(100000).nullable(),
  monthly_draft_limit: z.number().int().min(0).max(100000).nullable(),
  monthly_video_limit: z.number().int().min(0).max(100000).nullable(),
  monthly_merge_limit: z.number().int().min(0).max(100000).nullable(),
  daily_song_limit_per_channel: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
  daily_image_limit_per_channel: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
  daily_draft_limit_per_channel: z.number().int().min(1, 'Must be at least 1').max(10000, 'Max is 10000'),
  daily_video_limit: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
  daily_merge_limit: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
  billing_cycle_days: z.number().min(1, 'Billing cycle must be at least 1 day'),
});

type PlanUpdateFormValues = z.infer<typeof planUpdateSchema>;

const createPlanSchema = z.object({
  name: z.string().min(1, 'Name is required').max(50),
  price_cents: z.number().min(0, 'Price must be 0 or greater'),
  profile_allowance: z.number().min(1, 'Must be at least 1'),
  monthly_song_limit: z.number().int().min(0).max(100000).nullable(),
  monthly_image_limit: z.number().int().min(0).max(100000).nullable(),
  monthly_draft_limit: z.number().int().min(0).max(100000).nullable(),
  monthly_video_limit: z.number().int().min(0).max(100000).nullable(),
  monthly_merge_limit: z.number().int().min(0).max(100000).nullable(),
  billing_cycle_days: z.number().min(1, 'Must be at least 1 day'),
  daily_song_limit_per_channel: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
  daily_image_limit_per_channel: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
  daily_draft_limit_per_channel: z.number().int().min(1, 'Must be at least 1').max(10000, 'Max is 10000'),
  daily_video_limit: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
  daily_merge_limit: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
});

type CreatePlanFormValues = z.infer<typeof createPlanSchema>;

const createOfferSchema = z.object({
  plan_id: z.string().min(1, 'Plan ID is required'),
  promo_price_cents: z.number().min(0, 'Promo price must be 0 or greater'),
  max_redemptions: z.number().min(1, 'Max redemptions must be at least 1'),
});

type CreateOfferFormValues = z.infer<typeof createOfferSchema>;

// --- Helpers ---

function applyBillingTerm(
  monthlyCents: number,
  term: 'monthly' | 'semi' | 'annual',
  discounts?: { semiAnnualDiscountPercent?: number; annualDiscountPercent?: number },
): { price_cents: number; billing_cycle_days: number } {
  const quotes = billingTermQuotes(monthlyCents, discounts);
  if (term === 'semi') {
    return { price_cents: quotes[1]?.totalCents ?? monthlyCents, billing_cycle_days: 180 };
  }
  if (term === 'annual') {
    return { price_cents: quotes[2]?.totalCents ?? monthlyCents, billing_cycle_days: 365 };
  }
  return { price_cents: monthlyCents, billing_cycle_days: 30 };
}

function monthlyEquivalentFromPlan(
  priceCents: number,
  billingCycleDays: number,
  discounts?: { semiAnnualDiscountPercent?: number; annualDiscountPercent?: number },
): number {
  const semi = (discounts?.semiAnnualDiscountPercent ?? 15) / 100;
  const annual = (discounts?.annualDiscountPercent ?? 25) / 100;
  if (billingCycleDays === 30) return priceCents;
  if (billingCycleDays === 180) return Math.round(priceCents / 6 / (1 - semi));
  if (billingCycleDays === 365) return Math.round(priceCents / 12 / (1 - annual));
  return Math.round((priceCents / billingCycleDays) * 30);
}

// --- Component ---

export default function PlansPage() {
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [createPlanDialogOpen, setCreatePlanDialogOpen] = useState(false);
  const [createOfferDialogOpen, setCreateOfferDialogOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);
  const [deletePlanTarget, setDeletePlanTarget] = useState<Plan | null>(null);
  const [editSongUnlimited, setEditSongUnlimited] = useState(false);
  const [editImageUnlimited, setEditImageUnlimited] = useState(false);
  const [editDraftUnlimited, setEditDraftUnlimited] = useState(false);
  const [createSongUnlimited, setCreateSongUnlimited] = useState(false);
  const [createImageUnlimited, setCreateImageUnlimited] = useState(false);
  const [createDraftUnlimited, setCreateDraftUnlimited] = useState(false);
  const [createSemiDiscountPercent, setCreateSemiDiscountPercent] = useState(15);
  const [createAnnualDiscountPercent, setCreateAnnualDiscountPercent] = useState(25);

  const { data: plans, isLoading: plansLoading, isError: plansError, error: plansErr, refetch: refetchPlans } = usePlans();
  const { data: offers, isLoading: offersLoading, isError: offersError, error: offersErr, refetch: refetchOffers } = useOffers();
  const { data: termDiscounts } = usePlanTermDiscounts();
  const createPlan = useCreatePlan();
  const updatePlan = useUpdatePlan();
  const deletePlan = useDeletePlan();
  const createOffer = useCreateOffer();
  const subscriptionPlans = plans?.filter((plan) => plan.plan_kind !== 'profile_addon') ?? [];
  const twoChannelBasePlan = subscriptionPlans
    .filter(
      (plan) =>
        plan.is_active &&
        plan.profile_allowance === 2 &&
        plan.billing_cycle_days === 30,
    )
    .sort((a, b) => a.price_cents - b.price_cents)[0];
  const blockPriceCents = twoChannelBasePlan?.price_cents ?? 7900;

  useEffect(() => {
    if (!termDiscounts) return;
    setCreateSemiDiscountPercent(termDiscounts.semi_annual_discount_percent);
    setCreateAnnualDiscountPercent(termDiscounts.annual_discount_percent);
  }, [termDiscounts]);

  const handleTogglePlanActive = useCallback(
    (plan: Plan) => {
      updatePlan.mutate(
        { id: plan.id, updates: { is_active: !plan.is_active } },
        {
          onSuccess: () => {
            toast({ title: plan.is_active ? 'Plan deactivated' : 'Plan activated' });
          },
        },
      );
    },
    [updatePlan],
  );

  const editForm = useForm<PlanUpdateFormValues>({
    resolver: zodResolver(planUpdateSchema),
    defaultValues: {
      price_cents: 0,
      profile_allowance: 1,
      monthly_song_limit: 0,
      monthly_image_limit: 0,
      monthly_draft_limit: 0,
      monthly_video_limit: 300,
      monthly_merge_limit: 30,
      daily_song_limit_per_channel: 10,
      daily_image_limit_per_channel: 2,
      daily_draft_limit_per_channel: 21,
      daily_video_limit: 10,
      daily_merge_limit: 1,
      billing_cycle_days: 30,
    },
  });

  const createPlanForm = useForm<CreatePlanFormValues>({
    resolver: zodResolver(createPlanSchema),
    defaultValues: {
      name: '',
      price_cents: 0,
      profile_allowance: 1,
      monthly_song_limit: 300,
      monthly_image_limit: 120,
      monthly_draft_limit: 1260,
      monthly_video_limit: 300,
      monthly_merge_limit: 30,
      billing_cycle_days: 30,
      daily_song_limit_per_channel: 10,
      daily_image_limit_per_channel: 2,
      daily_draft_limit_per_channel: 21,
      daily_video_limit: 10,
      daily_merge_limit: 1,
    },
  });

  const offerForm = useForm<CreateOfferFormValues>({
    resolver: zodResolver(createOfferSchema),
    defaultValues: {
      plan_id: '',
      promo_price_cents: 0,
      max_redemptions: 100,
    },
  });

  const openCreatePlanDialog = useCallback(() => {
    createPlanForm.reset();
    if (termDiscounts) {
      setCreateSemiDiscountPercent(termDiscounts.semi_annual_discount_percent);
      setCreateAnnualDiscountPercent(termDiscounts.annual_discount_percent);
    }
    setCreatePlanDialogOpen(true);
  }, [createPlanForm, termDiscounts]);

  const openEditDialog = (plan: Plan) => {
    setSelectedPlan(plan);
    const songUnlimited = plan.monthly_song_limit === null;
    const imageUnlimited = plan.monthly_image_limit === null;
    const draftUnlimited = plan.monthly_draft_limit === null;
    setEditSongUnlimited(songUnlimited);
    setEditImageUnlimited(imageUnlimited);
    setEditDraftUnlimited(draftUnlimited);
    editForm.reset({
      price_cents: plan.price_cents,
      profile_allowance: plan.profile_allowance,
      monthly_song_limit: plan.monthly_song_limit,
      monthly_image_limit: plan.monthly_image_limit,
      monthly_draft_limit: plan.monthly_draft_limit,
      monthly_video_limit: plan.monthly_video_limit,
      monthly_merge_limit: plan.monthly_merge_limit,
      daily_song_limit_per_channel: plan.daily_song_limit_per_channel,
      daily_image_limit_per_channel: plan.daily_image_limit_per_channel,
      daily_draft_limit_per_channel: plan.daily_draft_limit_per_channel ?? 300,
      daily_video_limit: plan.daily_video_limit ?? 10,
      daily_merge_limit: plan.daily_merge_limit ?? 1,
      billing_cycle_days: plan.billing_cycle_days ?? 30,
    });
    setEditDialogOpen(true);
  };

  const handleCreatePlan = (values: CreatePlanFormValues) => {
    createPlan.mutate(
      {
        ...values,
        monthly_song_limit: createSongUnlimited ? null : values.monthly_song_limit,
        monthly_image_limit: createImageUnlimited ? null : values.monthly_image_limit,
        monthly_draft_limit: createDraftUnlimited ? null : values.monthly_draft_limit,
        daily_draft_limit_per_channel: values.daily_draft_limit_per_channel,
      },
      {
        onSuccess: () => {
          toast({ title: 'Plan created successfully' });
          setCreatePlanDialogOpen(false);
          createPlanForm.reset();
          setCreateSongUnlimited(false);
          setCreateImageUnlimited(false);
        },
        onError: (err) => {
          const axiosError = err as AxiosError<{ detail?: string }>;
          toast({
            title: 'Error',
            description: axiosError.response?.data?.detail ?? 'Failed to create plan',
            variant: 'destructive',
          });
        },
      },
    );
  };

  const handleUpdatePlan = (values: PlanUpdateFormValues) => {
    if (!selectedPlan) return;
    updatePlan.mutate(
      {
        id: selectedPlan.id,
        updates: {
          ...values,
          monthly_song_limit: editSongUnlimited ? null : values.monthly_song_limit,
          monthly_image_limit: editImageUnlimited ? null : values.monthly_image_limit,
          monthly_draft_limit: editDraftUnlimited ? null : values.monthly_draft_limit,
          daily_draft_limit_per_channel: values.daily_draft_limit_per_channel,
        },
      },
      {
        onSuccess: () => {
          toast({ title: 'Plan updated successfully' });
          setEditDialogOpen(false);
          setSelectedPlan(null);
        },
        onError: (err) => {
          const axiosError = err as AxiosError<{ detail?: string }>;
          toast({
            title: 'Error',
            description: axiosError.response?.data?.detail ?? 'Failed to update plan',
            variant: 'destructive',
          });
        },
      },
    );
  };

  const handleCreateOffer = (values: CreateOfferFormValues) => {
    createOffer.mutate(values, {
      onSuccess: () => {
        toast({ title: 'Offer created successfully' });
        setCreateOfferDialogOpen(false);
        offerForm.reset();
      },
      onError: (err) => {
        const axiosError = err as AxiosError<{ detail?: string }>;
        toast({
          title: 'Error',
          description: axiosError.response?.data?.detail ?? 'Failed to create offer',
          variant: 'destructive',
        });
      },
    });
  };

  const handleDeletePlan = () => {
    if (!deletePlanTarget) return;
    deletePlan.mutate(deletePlanTarget.id, {
      onSuccess: () => {
        toast({ title: 'Plan permanently deleted' });
        setDeletePlanTarget(null);
      },
      onError: (err) => {
        const axiosError = err as AxiosError<{
          detail?: string;
          error?: { message?: string };
        }>;
        toast({
          title: 'Error',
          description:
            axiosError.response?.data?.error?.message ??
            axiosError.response?.data?.detail ??
            'Failed to delete plan',
          variant: 'destructive',
        });
      },
    });
  };

  if (plansError && !plans) {
    return (
      <div className="p-6">
        <h1 className="mb-6 text-2xl font-bold text-slate-100">Plans</h1>
        <ErrorState
          message={plansErr?.message ?? 'Failed to load plans'}
          onRetry={() => refetchPlans()}
        />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-8">
      <h1 className="text-2xl font-bold text-slate-100">Plans</h1>

      <ChannelPricingSection />

      <SubscriptionPlansSection
        plans={subscriptionPlans}
        isLoading={plansLoading}
        onCreatePlan={openCreatePlanDialog}
        onEditPlan={openEditDialog}
        onToggleActive={handleTogglePlanActive}
        onDeletePlan={setDeletePlanTarget}
      />

      {/* Section 2: Promotional Offers */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Promotional Offers</CardTitle>
          <Button
            size="sm"
            onClick={() => {
              offerForm.reset();
              setCreateOfferDialogOpen(true);
            }}
          >
            Create Offer
          </Button>
        </CardHeader>
        <CardContent>
          {offersLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : offersError ? (
            <ErrorState
              message={offersErr?.message ?? 'Failed to load offers'}
              onRetry={() => refetchOffers()}
            />
          ) : offers?.length === 0 ? (
            <p className="py-4 text-center text-slate-400">No active offers.</p>
          ) : (
            <div className="space-y-4">
              {offers?.map((offer) => (
                <OfferCard key={offer.id} offer={offer} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Plan Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Plan</DialogTitle>
            <DialogDescription>
              Update plan settings for &quot;{selectedPlan?.name}&quot;
            </DialogDescription>
          </DialogHeader>
          <Form {...editForm}>
            <form onSubmit={editForm.handleSubmit(handleUpdatePlan)} className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <FormField
                  control={editForm.control}
                  name="price_cents"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Price (cents)</FormLabel>
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
                  control={editForm.control}
                  name="profile_allowance"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Channels</FormLabel>
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
                  control={editForm.control}
                  name="billing_cycle_days"
                  render={({ field }) => (
                    <FormItem className="md:col-span-2">
                      <FormLabel>Billing cycle (days)</FormLabel>
                      <div className="flex flex-wrap items-center gap-2">
                        <FormControl>
                          <Input
                            type="number"
                            className="max-w-[140px]"
                            {...field}
                            onChange={(e) => field.onChange(Number(e.target.value))}
                          />
                        </FormControl>
                        {(['monthly', 'semi', 'annual'] as const).map((term) => (
                          <Button
                            key={term}
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              const monthly = monthlyEquivalentFromPlan(
                                editForm.getValues('price_cents'),
                                editForm.getValues('billing_cycle_days'),
                              );
                              const applied = applyBillingTerm(monthly, term);
                              editForm.setValue('price_cents', applied.price_cents);
                              editForm.setValue('billing_cycle_days', applied.billing_cycle_days);
                            }}
                          >
                            {term === 'monthly' ? 'Monthly' : term === 'semi' ? '6 mo' : 'Annual'}
                          </Button>
                        ))}
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <PlanLimitsFields
                  control={editForm.control}
                  unlimited={{
                    song: editSongUnlimited,
                    setSong: setEditSongUnlimited,
                    image: editImageUnlimited,
                    setImage: setEditImageUnlimited,
                    draft: editDraftUnlimited,
                    setDraft: setEditDraftUnlimited,
                  }}
                />
              </div>
              <PlanPricingPreview
                priceCents={editForm.watch('price_cents')}
                profileAllowance={editForm.watch('profile_allowance')}
                billingCycleDays={editForm.watch('billing_cycle_days')}
                blockPriceCents={blockPriceCents}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setEditDialogOpen(false)}
                  disabled={updatePlan.isPending}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={updatePlan.isPending}>
                  {updatePlan.isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Save Changes
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Create Plan Dialog */}
      <Dialog open={createPlanDialogOpen} onOpenChange={setCreatePlanDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create New Plan</DialogTitle>
            <DialogDescription>
              Create a subscription plan row. Use term buttons to derive 6-month or annual checkout prices.
            </DialogDescription>
          </DialogHeader>
          <Form {...createPlanForm}>
            <form onSubmit={createPlanForm.handleSubmit(handleCreatePlan)} className="space-y-4">
              <FormField
                control={createPlanForm.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Plan Name</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="e.g., Monthly 6-channel" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={createPlanForm.control}
                name="profile_allowance"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Channels</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createPlanForm.control}
                name="price_cents"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Checkout price (cents)</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createPlanForm.control}
                name="billing_cycle_days"
                render={({ field }) => (
                  <FormItem className="md:col-span-2">
                    <FormLabel>Billing term &amp; discounts</FormLabel>
                    <p className="mb-3 text-xs text-slate-500">
                      Loaded from saved billing term discounts on this page. Adjust there first, or tweak here
                      for one-off calculator preview before creating the row.
                    </p>
                    <div className="mb-3 grid gap-3 sm:grid-cols-2">
                      <label className="space-y-1 text-sm">
                        <span className="text-slate-400">6-month discount (%)</span>
                        <Input
                          type="number"
                          min={0}
                          max={50}
                          value={createSemiDiscountPercent}
                          onChange={(e) => setCreateSemiDiscountPercent(Number(e.target.value))}
                        />
                      </label>
                      <label className="space-y-1 text-sm">
                        <span className="text-slate-400">Annual discount (%)</span>
                        <Input
                          type="number"
                          min={0}
                          max={50}
                          value={createAnnualDiscountPercent}
                          onChange={(e) => setCreateAnnualDiscountPercent(Number(e.target.value))}
                        />
                      </label>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <FormControl>
                        <Input
                          type="number"
                          className="max-w-[140px]"
                          {...field}
                          onChange={(e) => field.onChange(Number(e.target.value))}
                        />
                      </FormControl>
                      {(['monthly', 'semi', 'annual'] as const).map((term) => (
                        <Button
                          key={term}
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            const monthly = linearPlanMonthlyCents(
                              blockPriceCents,
                              createPlanForm.getValues('profile_allowance'),
                            );
                            const applied = applyBillingTerm(monthly, term, {
                              semiAnnualDiscountPercent: createSemiDiscountPercent,
                              annualDiscountPercent: createAnnualDiscountPercent,
                            });
                            createPlanForm.setValue('price_cents', applied.price_cents);
                            createPlanForm.setValue('billing_cycle_days', applied.billing_cycle_days);
                            createPlanForm.setValue(
                              'name',
                              formatChannelPlanName(
                                createPlanForm.getValues('profile_allowance'),
                                applied.billing_cycle_days,
                              ),
                            );
                          }}
                        >
                          {term === 'monthly' ? 'Monthly' : term === 'semi' ? '6 Months' : 'Annual'}
                        </Button>
                      ))}
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          createPlanForm.setValue(
                            'name',
                            formatChannelPlanName(
                              createPlanForm.getValues('profile_allowance'),
                              createPlanForm.getValues('billing_cycle_days'),
                            ),
                          );
                        }}
                      >
                        Use suggested name
                      </Button>
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <PlanLimitsFields
                control={createPlanForm.control}
                unlimited={{
                  song: createSongUnlimited,
                  setSong: setCreateSongUnlimited,
                  image: createImageUnlimited,
                  setImage: setCreateImageUnlimited,
                  draft: createDraftUnlimited,
                  setDraft: setCreateDraftUnlimited,
                }}
              />
              </div>
              <SmartPlanPriceCalculator
                blockPriceCents={blockPriceCents}
                profileAllowance={createPlanForm.watch('profile_allowance')}
                billingCycleDays={createPlanForm.watch('billing_cycle_days')}
                semiAnnualDiscountPercent={createSemiDiscountPercent}
                annualDiscountPercent={createAnnualDiscountPercent}
                onApplyPrice={(priceCents, billingCycleDays) => {
                  createPlanForm.setValue('price_cents', priceCents);
                  createPlanForm.setValue('billing_cycle_days', billingCycleDays);
                  createPlanForm.setValue(
                    'name',
                    formatChannelPlanName(createPlanForm.getValues('profile_allowance'), billingCycleDays),
                  );
                }}
              />
              <PlanPricingPreview
                priceCents={createPlanForm.watch('price_cents')}
                profileAllowance={createPlanForm.watch('profile_allowance')}
                billingCycleDays={createPlanForm.watch('billing_cycle_days')}
                blockPriceCents={blockPriceCents}
                semiAnnualDiscountPercent={createSemiDiscountPercent}
                annualDiscountPercent={createAnnualDiscountPercent}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setCreatePlanDialogOpen(false)} disabled={createPlan.isPending}>Cancel</Button>
                <Button type="submit" disabled={createPlan.isPending}>
                  {createPlan.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create Plan
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Create Offer Dialog */}
      <Dialog open={createOfferDialogOpen} onOpenChange={setCreateOfferDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Promotional Offer</DialogTitle>
            <DialogDescription>
              Create a new promotional offer for a plan.
            </DialogDescription>
          </DialogHeader>
          <Form {...offerForm}>
            <form onSubmit={offerForm.handleSubmit(handleCreateOffer)} className="space-y-4">
              <FormField
                control={offerForm.control}
                name="plan_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Plan ID</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="Enter plan ID" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={offerForm.control}
                name="promo_price_cents"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Promo Price (cents)</FormLabel>
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
                control={offerForm.control}
                name="max_redemptions"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Max Redemptions</FormLabel>
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
                  onClick={() => setCreateOfferDialogOpen(false)}
                  disabled={createOffer.isPending}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={createOffer.isPending}>
                  {createOffer.isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Create Offer
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
        title="Delete plan permanently?"
        description={
          deletePlanTarget
            ? `This will permanently delete "${deletePlanTarget.name}" and remove its unassigned licenses and offers. This cannot be undone.`
            : ''
        }
        onConfirm={handleDeletePlan}
        variant="destructive"
        confirmText="Delete Permanently"
        isLoading={deletePlan.isPending}
      />
    </div>
  );
}

// --- Offer Card Sub-Component ---

function OfferCard({ offer }: { offer: PlanOffer }) {
  const progressPercent = Math.round(
    (offer.current_redemptions / offer.max_redemptions) * 100,
  );

  return (
    <div className="rounded-lg border border-slate-700 p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="space-y-1">
          <p className="text-sm text-slate-300">
            Plan: <span className="font-medium text-slate-200">{offer.plan_id}</span>
          </p>
          <p className="text-sm text-slate-300">
            Promo Price: <span className="font-medium text-slate-200">{formatUsd(offer.promo_price_cents)}</span>
          </p>
        </div>
        <Badge
          variant="outline"
          className={
            offer.is_active
              ? 'border-green-500/30 bg-green-500/10 text-green-400'
              : 'border-red-500/30 bg-red-500/10 text-red-400'
          }
        >
          {offer.is_active ? 'Active' : 'Inactive'}
        </Badge>
      </div>
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Redemptions</span>
          <span>
            {offer.current_redemptions} / {offer.max_redemptions} ({progressPercent}%)
          </span>
        </div>
        <Progress value={progressPercent} className="h-2" />
      </div>
    </div>
  );
}
