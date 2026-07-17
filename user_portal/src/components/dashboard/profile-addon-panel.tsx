"use client";

import * as React from "react";
import Link from "next/link";
import { LoaderCircle, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import {
  createProfileAddonPayment,
  getProfileAddonQuote,
  type ProfileAddonQuote,
} from "@/lib/billing";
import type { CurrentUserResponse } from "@/lib/channel-setup";

function formatUsd(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);
}

type ProfileAddonPanelProps = {
  user: CurrentUserResponse;
  profileCount: number;
};

export function ProfileAddonPanel({ user, profileCount }: ProfileAddonPanelProps) {
  const [quote, setQuote] = React.useState<ProfileAddonQuote | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [checkingOut, setCheckingOut] = React.useState(false);

  const quotaChannels =
    user.effective_quota_channels ??
    (user.profile_allowance != null
      ? user.profile_allowance + (user.profile_addon_slots ?? 0)
      : null);
  const creationLimit =
    user.effective_profile_allowance ??
    (user.profile_allowance != null
      ? user.profile_allowance + (user.profile_addon_slots ?? 0) + (user.profile_addon_pending ?? 0)
      : null);
  const pending = user.profile_addon_pending ?? 0;

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getProfileAddonQuote(2)
      .then((result) => {
        if (!cancelled) setQuote(result);
      })
      .catch(() => {
        if (!cancelled) setQuote(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [quotaChannels]);

  async function handleCheckout() {
    setCheckingOut(true);
    try {
      const payment = await createProfileAddonPayment(2);
      window.location.href = payment.checkout_url;
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Checkout failed",
        description: err instanceof Error ? err.message : "Unable to start add-on checkout.",
      });
    } finally {
      setCheckingOut(false);
    }
  }

  const canBuyMore = quote != null && quote.max_addon_channels_remaining > 0;

  return (
    <div className="rounded-[28px] border border-emerald-400/15 bg-[linear-gradient(180deg,rgba(16,52,40,0.35),rgba(9,12,28,0.98))] p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-emerald-300/80">Channel add-ons</div>
          <div className="mt-2 font-display text-xl font-semibold text-white">+2 channel bundles</div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300/72">
            {profileCount} profile{profileCount === 1 ? "" : "s"} created ·{" "}
            {quotaChannels ?? "—"} active quota channel{(quotaChannels ?? 0) === 1 ? "" : "s"} ·{" "}
            {creationLimit ?? "—"} creation limit
            {pending > 0 ? ` · ${pending} pending onboarding` : ""}. Quotas increase only after you
            complete onboarding for new profiles.
          </p>
        </div>
        {pending >= 2 ? (
          <Button asChild className="shrink-0">
            <Link href="/onboarding?mode=addon">Complete add-on onboarding</Link>
          </Button>
        ) : canBuyMore ? (
          <Button
            type="button"
            className="shrink-0"
            disabled={checkingOut || loading}
            onClick={() => void handleCheckout()}
          >
            {checkingOut ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            Add 2 channels
            {quote ? ` · ${formatUsd(quote.monthly_addon_cents)} checkout` : ""}
          </Button>
        ) : null}
      </div>
      {loading ? (
        <div className="mt-4 text-sm text-slate-400">Loading add-on pricing…</div>
      ) : quote && canBuyMore ? (
        <div className="mt-4 text-sm text-slate-300/72">
          Next bundle: {quote.current_channels} → {quote.new_total_channels} channels · checkout{" "}
          {formatUsd(quote.monthly_addon_cents)} (aligned to your billing term). Pending slots let
          you create profiles only — quotas increase after onboarding completes.
        </div>
      ) : !canBuyMore && pending === 0 ? (
        <div className="mt-4 text-sm text-slate-400">You have reached the 10-channel account maximum.</div>
      ) : null}
    </div>
  );
}
