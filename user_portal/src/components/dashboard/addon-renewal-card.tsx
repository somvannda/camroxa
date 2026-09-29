"use client";

import * as React from "react";
import { Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  createAddonRenewal,
  getAddonRenewal,
  type AddonRenewal,
} from "@/lib/billing";

function formatUsd(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);
}

function formatCredits(value: number | null | undefined) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value ?? 0);
}

/**
 * Renew extra (add-on) channels. Channels never expire; renewing grants credits at
 * the plan rate so the user can keep running those channels without buying packs.
 */
export function AddonRenewalCard() {
  const [data, setData] = React.useState<AddonRenewal | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [buying, setBuying] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    getAddonRenewal()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading || !data?.eligible) {
    return null;
  }

  const canRenew = data.renewable !== false;
  const priceLabel = formatUsd(data.price_cents ?? 0);

  async function onRenew() {
    setBuying(true);
    setError(null);
    try {
      const payment = await createAddonRenewal();
      if (payment.checkout_url) {
        window.location.href = payment.checkout_url;
        return;
      }
      setError("Checkout could not be started. Please try again.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start add-on renewal.");
    } finally {
      setBuying(false);
    }
  }

  return (
    <Card className="rounded-[28px] border-emerald-400/20 bg-[linear-gradient(135deg,rgba(16,52,40,0.30),rgba(10,14,34,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.28)]">
      <CardHeader>
        <CardTitle className="font-display text-2xl text-white">
          Renew add-on channels ({data.addon_channels} extra)
        </CardTitle>
        <CardDescription className="text-slate-300/80">
          {canRenew
            ? `Renew for ${priceLabel} and add ${formatCredits(data.credits)} credits at the plan rate. Your channels stay either way.`
            : `Renewal opens ${data.renewal_window_days} days before your plan ends — ${
                data.renewal_opens_in_days ?? 0
              } day${(data.renewal_opens_in_days ?? 0) === 1 ? "" : "s"} to go.`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button
          type="button"
          disabled={buying || !canRenew}
          onClick={() => void onRenew()}
          className="h-11 bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600"
        >
          {buying ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          {canRenew
            ? `Renew ${data.addon_channels} channels · ${priceLabel} → +${formatCredits(data.credits)} credits`
            : `Renewal opens in ${data.renewal_opens_in_days ?? 0}d`}
        </Button>
        {error ? <p className="mt-3 text-sm text-rose-300">{error}</p> : null}
      </CardContent>
    </Card>
  );
}
