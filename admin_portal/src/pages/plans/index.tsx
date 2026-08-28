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
import { useOffers, useCreateOffer } from '@/hooks/use-plans';
import { formatUsd } from '@/lib/plan-tier-pricing';
import { CreditsOnlySection } from '@/pages/plans/credits-only-section';
import { toast } from '@/hooks/use-toast';
import type { PlanOffer } from '@/types/models';

const createOfferSchema = z.object({
  plan_id: z.string().min(1, 'Plan ID is required'),
  promo_price_cents: z.number().min(0, 'Promo price must be 0 or greater'),
  max_redemptions: z.number().min(1, 'Max redemptions must be at least 1'),
});

type CreateOfferFormValues = z.infer<typeof createOfferSchema>;

export default function PlansPage() {
  const [createOfferDialogOpen, setCreateOfferDialogOpen] = useState(false);

  const { data: offers, isLoading: offersLoading, isError: offersError, error: offersErr, refetch: refetchOffers } = useOffers();
  const createOffer = useCreateOffer();

  const offerForm = useForm<CreateOfferFormValues>({
    resolver: zodResolver(createOfferSchema),
    defaultValues: {
      plan_id: '',
      promo_price_cents: 0,
      max_redemptions: 100,
    },
  });

  const handleCreateOffer = (values: CreateOfferFormValues) => {
    createOffer.mutate(values, {
      onSuccess: () => {
        toast({ title: 'Offer created' });
        setCreateOfferDialogOpen(false);
        offerForm.reset();
      },
      onError: (err) => {
        const axiosError = err as AxiosError<{ detail?: string }>;
        toast({
          title: 'Could not create offer',
          description: axiosError.response?.data?.detail ?? 'Failed to create offer',
          variant: 'destructive',
        });
      },
    });
  };

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Plans</h1>
        <p className="mt-1 text-sm text-slate-400">
          Credits-only catalog. Plans grant credits. Generate charges the Credits page.
        </p>
      </div>

      <CreditsOnlySection />

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
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : offersError ? (
            <ErrorState
              message={offersErr?.message ?? 'Failed to load offers'}
              onRetry={() => refetchOffers()}
            />
          ) : !offers?.length ? (
            <p className="text-sm text-slate-400">No promotional offers.</p>
          ) : (
            <div className="space-y-3">
              {offers.map((offer) => (
                <OfferCard key={offer.id} offer={offer} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

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
