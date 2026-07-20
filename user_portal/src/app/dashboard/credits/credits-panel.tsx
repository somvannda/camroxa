"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Coins, TicketPercent } from "lucide-react";

import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  EmptyPanel,
  RedeemHistoryRow,
  SectionTitle,
  SummaryRow,
  formatCreditValue,
  formatNumber,
} from "@/components/dashboard/control-panel-ui";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import {
  createCreditPackPayment,
  getBillingPayment,
  resolveBillingPaymentByExternalId,
} from "@/lib/billing";
import { listCreditPacks, type CreditPack } from "@/lib/credit-packs";
import {
  clearPendingRedeemCode,
  loadPendingRedeemCode,
  redeemUserCode,
  savePendingRedeemCode,
} from "@/lib/redeem-codes";

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

type CreditsPanelProps = {
  returnedPaymentId?: string | null;
  returnedPaymentStatus?: string | null;
  embedded?: boolean;
};

export function CreditsPanel({
  returnedPaymentId = null,
  returnedPaymentStatus = null,
  embedded = false,
}: CreditsPanelProps) {
  const router = useRouter();
  const { state, refreshCreditsAndActivity } = useControlPanel();
  const [redeemCode, setRedeemCode] = React.useState("");
  const [redeeming, setRedeeming] = React.useState(false);
  const [packs, setPacks] = React.useState<CreditPack[]>([]);
  const [packCheckoutId, setPackCheckoutId] = React.useState<string | null>(null);
  const [pendingPaymentId, setPendingPaymentId] = React.useState<string | null>(null);
  const [checkingPayment, setCheckingPayment] = React.useState(false);
  const handledCheckoutReturnRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    setRedeemCode(loadPendingRedeemCode());
    listCreditPacks()
      .then(setPacks)
      .catch(() => setPacks([]));
  }, []);

  const refreshPendingPayment = React.useCallback(
    async (showSuccessToast: boolean, paymentIdOverride?: string) => {
      const targetPaymentId = paymentIdOverride ?? pendingPaymentId;
      if (!targetPaymentId) return;

      setCheckingPayment(true);
      try {
        const payment = isUuid(targetPaymentId)
          ? await getBillingPayment(targetPaymentId)
          : await resolveBillingPaymentByExternalId(targetPaymentId);

        setPendingPaymentId(payment.id);

        if (payment.status === "paid" && payment.fulfilled_at) {
          setPendingPaymentId(null);
          await refreshCreditsAndActivity();
          if (showSuccessToast) {
            toast({
              title: "Credits added",
              description: `${payment.plan_name} has been added to your wallet.`,
            });
          }
          return;
        }

        if (payment.status === "expired" || payment.status === "failed") {
          setPendingPaymentId(null);
          toast({
            variant: "destructive",
            title: payment.status === "expired" ? "Payment expired" : "Payment failed",
            description: "Start a new checkout when you are ready.",
          });
          return;
        }

        if (showSuccessToast) {
          toast({
            title: "Payment still pending",
            description: "We are still waiting for provider confirmation.",
          });
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unable to refresh payment status.";
        if (showSuccessToast) {
          toast({ variant: "destructive", title: "Payment check failed", description: message });
        }
      } finally {
        setCheckingPayment(false);
      }
    },
    [pendingPaymentId, refreshCreditsAndActivity],
  );

  React.useEffect(() => {
    if (!returnedPaymentId) {
      return;
    }
    if (handledCheckoutReturnRef.current === returnedPaymentId) {
      return;
    }

    handledCheckoutReturnRef.current = returnedPaymentId;

    (async () => {
      let localPaymentId = returnedPaymentId;
      try {
        if (!isUuid(returnedPaymentId)) {
          const resolved = await resolveBillingPaymentByExternalId(returnedPaymentId);
          localPaymentId = resolved.id;
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unable to resolve checkout return.";
        toast({ variant: "destructive", title: "Payment return failed", description: message });
        router.replace("/dashboard/credits");
        return;
      }

      setPendingPaymentId(localPaymentId);
      router.replace(embedded ? "/dashboard/billing?tab=credits" : "/dashboard/credits");

      if (returnedPaymentStatus === "failed") {
        toast({
          variant: "destructive",
          title: "Payment failed",
          description: "Your KHQR payment did not complete. Try again when ready.",
        });
        return;
      }

      void refreshPendingPayment(true, localPaymentId);
    })();
  }, [refreshPendingPayment, returnedPaymentId, returnedPaymentStatus, router]);

  React.useEffect(() => {
    if (!pendingPaymentId) {
      return;
    }

    const initialRefresh = window.setTimeout(() => {
      void refreshPendingPayment(false);
    }, 0);
    const timer = window.setInterval(() => {
      void refreshPendingPayment(false);
    }, 5000);
    return () => {
      window.clearTimeout(initialRefresh);
      window.clearInterval(timer);
    };
  }, [pendingPaymentId, refreshPendingPayment]);

  if (!state.user) {
    return null;
  }

  const walletBalance = state.wallet?.balance ?? state.user.credit_balance ?? 0;
  const recentRedemptions = state.redemptions.slice(0, 8);

  async function handleRedeem() {
    const normalizedCode = redeemCode.trim().toUpperCase();
    if (!normalizedCode) {
      toast({
        variant: "destructive",
        title: "Redeem code required",
        description: "Enter a credit grant code to redeem it in your account.",
      });
      return;
    }

    setRedeeming(true);
    try {
      const result = await redeemUserCode(normalizedCode);
      clearPendingRedeemCode();
      setRedeemCode("");
      await refreshCreditsAndActivity();
      toast({
        title: "Credits added",
        description: result.message ?? "Your wallet balance has been updated.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to redeem this code.";
      toast({ variant: "destructive", title: "Redeem failed", description: message });
    } finally {
      setRedeeming(false);
    }
  }

  async function handlePackCheckout(packId: string) {
    setPackCheckoutId(packId);
    try {
      const payment = await createCreditPackPayment(packId);
      setPendingPaymentId(payment.id);
      window.location.href = payment.checkout_url;
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Checkout failed",
        description: err instanceof Error ? err.message : "Unable to start credit pack checkout.",
      });
    } finally {
      setPackCheckoutId(null);
    }
  }

  return (
    <div className="grid gap-5">
      {!embedded ? (
        <SectionTitle
          title="Credits"
          description="Wallet balance, credit-pack redeem, and plan quota snapshot."
        />
      ) : null}

      {checkingPayment ? (
        <div className="rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-300/80">
          Confirming your CutLuy payment and minting credits…
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(17,24,56,0.96),rgba(8,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.28)]">
          <CardHeader className="space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle className="font-display text-2xl text-white">Redeem credits</CardTitle>
                <CardDescription className="mt-2 text-slate-300/72">
                  Apply wallet credit-pack codes here. Discount codes still apply during checkout.
                </CardDescription>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-violet-400/25 bg-violet-500/10">
                <TicketPercent className="h-5 w-5 text-violet-200" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                Current wallet balance
              </div>
              <div className="flex items-center gap-2 text-3xl font-semibold text-white">
                <Coins className="h-6 w-6 text-emerald-300" />
                {formatCreditValue(walletBalance)}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
              <Input
                value={redeemCode}
                onChange={(event) => {
                  const nextCode = event.target.value.toUpperCase();
                  setRedeemCode(nextCode);
                  savePendingRedeemCode(nextCode);
                }}
                placeholder="Enter credit redeem code"
                className="border-white/10 bg-white/[0.04] text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
              />
              <Button onClick={() => void handleRedeem()} disabled={redeeming}>
                {redeeming ? "Redeeming..." : "Redeem code"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
          <CardHeader>
            <CardTitle className="font-display text-2xl text-white">Credit overview</CardTitle>
            <CardDescription className="text-slate-300/72">
              Wallet balance and plan quota snapshot.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm text-slate-300/72">
            <SummaryRow
              label="Credits total"
              value={formatCreditValue(state.stats?.credits_total ?? walletBalance)}
            />
            <SummaryRow
              label="Credits remaining"
              value={formatCreditValue(state.stats?.credits_remaining ?? walletBalance)}
            />
            <SummaryRow
              label="Credits spent"
              value={formatCreditValue(state.stats?.credits_spent ?? 0)}
            />
            <SummaryRow
              label="Drafts remaining"
              value={
                state.quota?.drafts_remaining !== null &&
                state.quota?.drafts_remaining !== undefined
                  ? `${formatNumber(state.quota.drafts_remaining)}${
                      state.quota.drafts_quota != null
                        ? ` / ${formatNumber(state.quota.drafts_quota)}`
                        : ""
                    }`
                  : "Not available"
              }
            />
            <SummaryRow
              label="Suno packages remaining"
              value={
                state.quota?.songs_remaining !== null &&
                state.quota?.songs_remaining !== undefined
                  ? `${formatNumber(state.quota.songs_remaining)}${
                      state.quota.songs_quota != null
                        ? ` / ${formatNumber(state.quota.songs_quota)}`
                        : ""
                    }`
                  : "Not available"
              }
            />
            <SummaryRow
              label="Images remaining"
              value={
                state.quota?.images_remaining !== null &&
                state.quota?.images_remaining !== undefined
                  ? `${formatNumber(state.quota.images_remaining)}${
                      state.quota.images_quota != null
                        ? ` / ${formatNumber(state.quota.images_quota)}`
                        : ""
                    }`
                  : "Not available"
              }
            />
            <SummaryRow
              label="Track exports remaining (month)"
              value={
                state.quota?.videos_remaining !== null &&
                state.quota?.videos_remaining !== undefined
                  ? `${formatNumber(state.quota.videos_remaining)}${
                      state.quota.videos_quota != null
                        ? ` / ${formatNumber(state.quota.videos_quota)}`
                        : ""
                    }`
                  : "Not available"
              }
            />
            <SummaryRow
              label="Merges remaining (month)"
              value={
                state.quota?.merges_remaining !== null &&
                state.quota?.merges_remaining !== undefined
                  ? `${formatNumber(state.quota.merges_remaining)}${
                      state.quota.merges_quota != null
                        ? ` / ${formatNumber(state.quota.merges_quota)}`
                        : ""
                    }`
                  : "Not available"
              }
            />
            <SummaryRow
              label="Track exports remaining (today)"
              value={
                state.quota?.daily_videos_remaining !== null &&
                state.quota?.daily_videos_remaining !== undefined
                  ? `${formatNumber(state.quota.daily_videos_remaining)}${
                      state.quota.daily_videos_limit != null
                        ? ` / ${formatNumber(state.quota.daily_videos_limit)}`
                        : ""
                    }`
                  : "Not available"
              }
            />
            <SummaryRow
              label="Merges remaining (today)"
              value={
                state.quota?.daily_merges_remaining !== null &&
                state.quota?.daily_merges_remaining !== undefined
                  ? `${formatNumber(state.quota.daily_merges_remaining)}${
                      state.quota.daily_merges_limit != null
                        ? ` / ${formatNumber(state.quota.daily_merges_limit)}`
                        : ""
                    }`
                  : "Not available"
              }
            />
            <SummaryRow
              label="Plan quota remaining"
              value={
                state.wallet?.plan_quota_remaining !== null &&
                state.wallet?.plan_quota_remaining !== undefined
                  ? formatCreditValue(state.wallet.plan_quota_remaining)
                  : "Not available"
              }
            />
          </CardContent>
        </Card>
      </div>

      {packs.length > 0 ? (
        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
          <CardHeader>
            <CardTitle className="font-display text-2xl text-white">Buy credit packs</CardTitle>
            <CardDescription className="text-slate-300/72">
              Wallet top-ups via CutLuy checkout. Credits mint after payment confirmation.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {packs.map((pack) => (
              <div
                key={pack.id}
                className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300/80"
              >
                <div className="font-medium text-white">{pack.name}</div>
                <div className="mt-2">
                  {formatCreditValue(pack.song_credits)} credits ·{" "}
                  {new Intl.NumberFormat("en-US", {
                    style: "currency",
                    currency: "USD",
                    maximumFractionDigits: 0,
                  }).format(pack.price_cents / 100)}
                </div>
                <Button
                  type="button"
                  className="mt-4"
                  disabled={packCheckoutId === pack.id}
                  onClick={() => void handlePackCheckout(pack.id)}
                >
                  {packCheckoutId === pack.id ? "Starting checkout…" : "Buy with CutLuy"}
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(17,24,56,0.96),rgba(8,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.28)]">
        <CardHeader>
          <CardTitle className="font-display text-2xl text-white">Redeem history</CardTitle>
          <CardDescription className="text-slate-300/72">
            Latest codes applied to your wallet or checkout.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {recentRedemptions.length > 0 ? (
            recentRedemptions.map((item) => (
              <RedeemHistoryRow key={item.id} item={item} />
            ))
          ) : (
            <EmptyPanel text="No redeem history yet." />
          )}
        </CardContent>
      </Card>

      {state.quota?.channels?.length ? (
        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
          <CardHeader>
            <CardTitle className="font-display text-2xl text-white">Daily channel limits</CardTitle>
            <CardDescription className="text-slate-300/72">
              Per-channel song and image capacity remaining today.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {state.quota.channels.map((channel) => (
              <div
                key={channel.profile_id}
                className="rounded-[20px] border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300/80"
              >
                <div className="font-medium text-white">{channel.profile_name}</div>
                <div className="mt-2 grid gap-1 md:grid-cols-2">
                  <div>
                    Songs today: {channel.daily_songs_remaining} / {channel.daily_songs_limit}{" "}
                    remaining
                  </div>
                  <div>
                    Images today: {channel.daily_images_remaining} / {channel.daily_images_limit}{" "}
                    remaining
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
