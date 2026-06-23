import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { AxiosError } from 'axios';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

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
import { usePlans, useCreatePlan, useUpdatePlan, useOffers, useCreateOffer } from '@/hooks/use-plans';
import { toast } from '@/hooks/use-toast';
import type { Plan, PlanOffer } from '@/types/models';

// --- Zod Schemas ---

const planUpdateSchema = z.object({
  price_cents: z.number().min(0, 'Price must be 0 or greater'),
  profile_allowance: z.number().min(1, 'Profile allowance must be at least 1'),
  monthly_song_limit: z.number().int().min(0).max(100000).nullable(),
  monthly_image_limit: z.number().int().min(0).max(100000).nullable(),
  daily_song_limit_per_channel: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
  daily_image_limit_per_channel: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
  billing_cycle_days: z.number().min(1, 'Billing cycle must be at least 1 day'),
});

type PlanUpdateFormValues = z.infer<typeof planUpdateSchema>;

const createPlanSchema = z.object({
  name: z.string().min(1, 'Name is required').max(50),
  price_cents: z.number().min(0, 'Price must be 0 or greater'),
  profile_allowance: z.number().min(1, 'Must be at least 1'),
  monthly_song_limit: z.number().int().min(0).max(100000).nullable(),
  monthly_image_limit: z.number().int().min(0).max(100000).nullable(),
  billing_cycle_days: z.number().min(1, 'Must be at least 1 day'),
  daily_song_limit_per_channel: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
  daily_image_limit_per_channel: z.number().int().min(1, 'Must be at least 1').max(1000, 'Max is 1000'),
});

type CreatePlanFormValues = z.infer<typeof createPlanSchema>;

const createOfferSchema = z.object({
  plan_id: z.string().min(1, 'Plan ID is required'),
  promo_price_cents: z.number().min(0, 'Promo price must be 0 or greater'),
  max_redemptions: z.number().min(1, 'Max redemptions must be at least 1'),
});

type CreateOfferFormValues = z.infer<typeof createOfferSchema>;

// --- Helpers ---

function formatPrice(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

// --- Component ---

export default function PlansPage() {
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [createPlanDialogOpen, setCreatePlanDialogOpen] = useState(false);
  const [createOfferDialogOpen, setCreateOfferDialogOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);
  const [editSongUnlimited, setEditSongUnlimited] = useState(false);
  const [editImageUnlimited, setEditImageUnlimited] = useState(false);
  const [createSongUnlimited, setCreateSongUnlimited] = useState(false);
  const [createImageUnlimited, setCreateImageUnlimited] = useState(false);

  const { data: plans, isLoading: plansLoading, isError: plansError, error: plansErr, refetch: refetchPlans } = usePlans();
  const { data: offers, isLoading: offersLoading, isError: offersError, error: offersErr, refetch: refetchOffers } = useOffers();
  const createPlan = useCreatePlan();
  const updatePlan = useUpdatePlan();
  const createOffer = useCreateOffer();

  const editForm = useForm<PlanUpdateFormValues>({
    resolver: zodResolver(planUpdateSchema),
    defaultValues: {
      price_cents: 0,
      profile_allowance: 1,
      monthly_song_limit: 0,
      monthly_image_limit: 0,
      daily_song_limit_per_channel: 7,
      daily_image_limit_per_channel: 7,
      billing_cycle_days: 30,
    },
  });

  const createPlanForm = useForm<CreatePlanFormValues>({
    resolver: zodResolver(createPlanSchema),
    defaultValues: {
      name: '',
      price_cents: 0,
      profile_allowance: 1,
      monthly_song_limit: 0,
      monthly_image_limit: 0,
      billing_cycle_days: 30,
      daily_song_limit_per_channel: 7,
      daily_image_limit_per_channel: 7,
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

  const openEditDialog = (plan: Plan) => {
    setSelectedPlan(plan);
    const songUnlimited = plan.monthly_song_limit === null;
    const imageUnlimited = plan.monthly_image_limit === null;
    setEditSongUnlimited(songUnlimited);
    setEditImageUnlimited(imageUnlimited);
    editForm.reset({
      price_cents: plan.price_cents,
      profile_allowance: plan.profile_allowance,
      monthly_song_limit: plan.monthly_song_limit,
      monthly_image_limit: plan.monthly_image_limit,
      daily_song_limit_per_channel: plan.daily_song_limit_per_channel,
      daily_image_limit_per_channel: plan.daily_image_limit_per_channel,
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

      {/* Section 1: Plans */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Subscription Plans</CardTitle>
          <Button size="sm" onClick={() => { createPlanForm.reset(); setCreatePlanDialogOpen(true); }}>
            Create Plan
          </Button>
        </CardHeader>
        <CardContent>
          {plansLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-slate-400">
                    <th className="pb-3 pr-4 font-medium">Name</th>
                    <th className="pb-3 pr-4 font-medium">Price</th>
                    <th className="pb-3 pr-4 font-medium">Profiles</th>
                    <th className="pb-3 pr-4 font-medium">Monthly Song Limit</th>
                    <th className="pb-3 pr-4 font-medium">Monthly Image Limit</th>
                    <th className="pb-3 pr-4 font-medium">Daily Song Limit</th>
                    <th className="pb-3 pr-4 font-medium">Daily Image Limit</th>
                    <th className="pb-3 pr-4 font-medium">Status</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {plans?.map((plan) => (
                    <tr
                      key={plan.id}
                      className="border-b border-slate-800 hover:bg-slate-800/50"
                    >
                      <td className="py-3 pr-4 text-slate-200">{plan.name}</td>
                      <td className="py-3 pr-4 text-slate-300">
                        {formatPrice(plan.price_cents)}
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        {plan.profile_allowance}
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        {plan.monthly_song_limit ?? '∞'}
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        {plan.monthly_image_limit ?? '∞'}
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        {plan.daily_song_limit_per_channel}
                      </td>
                      <td className="py-3 pr-4 text-slate-300">
                        {plan.daily_image_limit_per_channel}
                      </td>
                      <td className="py-3 pr-4">
                        <Badge
                          variant="outline"
                          className={
                            plan.is_active
                              ? 'border-green-500/30 bg-green-500/10 text-green-400'
                              : 'border-red-500/30 bg-red-500/10 text-red-400'
                          }
                        >
                          {plan.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="py-3">
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openEditDialog(plan)}
                          >
                            Edit
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className={plan.is_active
                              ? 'border-red-500/30 text-red-400 hover:bg-red-500/10'
                              : 'border-green-500/30 text-green-400 hover:bg-green-500/10'
                            }
                            onClick={() => {
                              updatePlan.mutate(
                                { id: plan.id, updates: { is_active: !plan.is_active } },
                                {
                                  onSuccess: () => {
                                    toast({ title: plan.is_active ? 'Plan deactivated' : 'Plan activated' });
                                  },
                                },
                              );
                            }}
                          >
                            {plan.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {plans?.length === 0 && (
                <p className="py-8 text-center text-slate-400">No plans found.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

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
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Plan</DialogTitle>
            <DialogDescription>
              Update plan settings for &quot;{selectedPlan?.name}&quot;
            </DialogDescription>
          </DialogHeader>
          <Form {...editForm}>
            <form onSubmit={editForm.handleSubmit(handleUpdatePlan)} className="space-y-4">
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
                    <FormLabel>Profile Allowance</FormLabel>
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
                name="monthly_song_limit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Monthly Song Limit</FormLabel>
                    <div className="flex items-center gap-3">
                      <FormControl>
                        <Input
                          type="number"
                          disabled={editSongUnlimited}
                          value={editSongUnlimited ? '' : (field.value ?? 0)}
                          onChange={(e) => field.onChange(Number(e.target.value))}
                          placeholder={editSongUnlimited ? 'Unlimited' : ''}
                        />
                      </FormControl>
                      <label className="flex items-center gap-1.5 text-sm text-slate-300 whitespace-nowrap">
                        <input
                          type="checkbox"
                          checked={editSongUnlimited}
                          onChange={(e) => {
                            setEditSongUnlimited(e.target.checked);
                            if (e.target.checked) {
                              field.onChange(null);
                            } else {
                              field.onChange(0);
                            }
                          }}
                          className="h-4 w-4 rounded border-slate-600"
                        />
                        Unlimited
                      </label>
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={editForm.control}
                name="monthly_image_limit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Monthly Image Limit</FormLabel>
                    <div className="flex items-center gap-3">
                      <FormControl>
                        <Input
                          type="number"
                          disabled={editImageUnlimited}
                          value={editImageUnlimited ? '' : (field.value ?? 0)}
                          onChange={(e) => field.onChange(Number(e.target.value))}
                          placeholder={editImageUnlimited ? 'Unlimited' : ''}
                        />
                      </FormControl>
                      <label className="flex items-center gap-1.5 text-sm text-slate-300 whitespace-nowrap">
                        <input
                          type="checkbox"
                          checked={editImageUnlimited}
                          onChange={(e) => {
                            setEditImageUnlimited(e.target.checked);
                            if (e.target.checked) {
                              field.onChange(null);
                            } else {
                              field.onChange(0);
                            }
                          }}
                          className="h-4 w-4 rounded border-slate-600"
                        />
                        Unlimited
                      </label>
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={editForm.control}
                name="daily_song_limit_per_channel"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Daily Song Limit Per Channel (1–1000)</FormLabel>
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
                name="daily_image_limit_per_channel"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Daily Image Limit Per Channel (1–1000)</FormLabel>
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
                  <FormItem>
                    <FormLabel>Billing Cycle (days)</FormLabel>
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
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Plan</DialogTitle>
            <DialogDescription>
              Create a new subscription plan (Monthly, Yearly, or Lifetime).
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
                      <Input {...field} placeholder="e.g., Monthly, Yearly, Lifetime" />
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
                    <FormLabel>Price (cents)</FormLabel>
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
                  <FormItem>
                    <FormLabel>Billing Cycle (days) — 30 for Monthly, 365 for Yearly</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createPlanForm.control}
                name="profile_allowance"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Profile Allowance</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createPlanForm.control}
                name="monthly_song_limit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Monthly Song Limit</FormLabel>
                    <div className="flex items-center gap-3">
                      <FormControl>
                        <Input
                          type="number"
                          disabled={createSongUnlimited}
                          value={createSongUnlimited ? '' : (field.value ?? 0)}
                          onChange={(e) => field.onChange(Number(e.target.value))}
                          placeholder={createSongUnlimited ? 'Unlimited' : ''}
                        />
                      </FormControl>
                      <label className="flex items-center gap-1.5 text-sm text-slate-300 whitespace-nowrap">
                        <input
                          type="checkbox"
                          checked={createSongUnlimited}
                          onChange={(e) => {
                            setCreateSongUnlimited(e.target.checked);
                            if (e.target.checked) {
                              field.onChange(null);
                            } else {
                              field.onChange(0);
                            }
                          }}
                          className="h-4 w-4 rounded border-slate-600"
                        />
                        Unlimited
                      </label>
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createPlanForm.control}
                name="monthly_image_limit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Monthly Image Limit</FormLabel>
                    <div className="flex items-center gap-3">
                      <FormControl>
                        <Input
                          type="number"
                          disabled={createImageUnlimited}
                          value={createImageUnlimited ? '' : (field.value ?? 0)}
                          onChange={(e) => field.onChange(Number(e.target.value))}
                          placeholder={createImageUnlimited ? 'Unlimited' : ''}
                        />
                      </FormControl>
                      <label className="flex items-center gap-1.5 text-sm text-slate-300 whitespace-nowrap">
                        <input
                          type="checkbox"
                          checked={createImageUnlimited}
                          onChange={(e) => {
                            setCreateImageUnlimited(e.target.checked);
                            if (e.target.checked) {
                              field.onChange(null);
                            } else {
                              field.onChange(0);
                            }
                          }}
                          className="h-4 w-4 rounded border-slate-600"
                        />
                        Unlimited
                      </label>
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createPlanForm.control}
                name="daily_song_limit_per_channel"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Daily Song Limit Per Channel (1–1000)</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createPlanForm.control}
                name="daily_image_limit_per_channel"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Daily Image Limit Per Channel (1–1000)</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} onChange={(e) => field.onChange(Number(e.target.value))} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
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
            Promo Price: <span className="font-medium text-slate-200">{formatPrice(offer.promo_price_cents)}</span>
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
