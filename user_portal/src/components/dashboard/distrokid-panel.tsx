"use client";

import * as React from "react";
import { LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import {
  createDistroKidPayment,
  getDistroKidStatus,
  type DistroKidStatus,
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

type DistroKidPanelProps = {
  user: CurrentUserResponse;
};

export function DistroKidPanel({ user }: DistroKidPanelProps) {
  const [status, setStatus] = React.useState<DistroKidStatus | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [checkingOut, setCheckingOut] = React.useState(false);

  const activeFromUser = Boolean(user.distrokid_active);
  const priceCents = status?.distrokid_price_cents ?? user.distrokid_price_cents ?? 500;
  const wavLimit =
    status?.distrokid_monthly_wav_limit ?? user.distrokid_monthly_wav_limit ?? 600;

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getDistroKidStatus()
      .then((result) => {
        if (!cancelled) setStatus(result);
      })
      .catch(() => {
        if (!cancelled) setStatus(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user.id, user.distrokid_active]);

  async function handleCheckout() {
    setCheckingOut(true);
    try {
      const payment = await createDistroKidPayment();
      window.location.href = payment.checkout_url;
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Checkout failed",
        description: err instanceof Error ? err.message : "Unable to start DistroKid checkout.",
      });
    } finally {
      setCheckingOut(false);
    }
  }

  const active = status?.distrokid_active ?? activeFromUser;

  return (
    <div className="rounded-[28px] border border-violet-400/15 bg-[linear-gradient(180deg,rgba(56,30,90,0.35),rgba(9,12,28,0.98))] p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-violet-300/80">Distribution</div>
          <div className="mt-2 font-display text-xl font-semibold text-white">DistroKid add-on</div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300/72">
            {formatUsd(priceCents)}/month · up to {wavLimit} WAV conversions (Primary + Secondary) ·
            DistroKid upload via the desktop app (Music DistroKid checkbox). Unlocks
            Suno WAV conversion (up to {wavLimit}/mo) and automated DistroKid delivery.
          </p>
          {active ? (
            <p className="mt-3 text-sm text-emerald-300/90">
              Active
              {status?.distrokid_expires_at
                ? ` · expires ${new Date(status.distrokid_expires_at).toLocaleString()}`
                : ""}
            </p>
          ) : (
            <p className="mt-3 text-sm text-slate-400">Not active on this subscription.</p>
          )}
        </div>
        {loading ? (
          <Button type="button" disabled className="shrink-0">
            <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
            Checking…
          </Button>
        ) : active ? null : (
          <Button type="button" className="shrink-0" disabled={checkingOut} onClick={handleCheckout}>
            {checkingOut ? (
              <>
                <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
                Starting…
              </>
            ) : (
              `Add DistroKid · ${formatUsd(priceCents)}`
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
