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
  createQuotaRenewal,
  getQuotaRenewal,
  type BillingPayment,
  type QuotaRenewal,
} from "@/lib/billing";

function formatCurrency(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

function formatExpiry(value?: string | null) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) {
    return null;
  }
  return date.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
}

/**
 * Renew card for the signed-in user's own plan.
 *
 * Uses `/billing/renewals/quota`, which resolves the plan from the user's license
 * (hidden legacy plans such as the $79 desktop plan included), so the plan stays
 * out of the public catalog while its owner can still pay for the next cycle.
 */
export function QuotaRenewalCard() {
  const [renewal, setRenewal] = React.useState<QuotaRenewal | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [purchasing, setPurchasing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const result = await getQuotaRenewal();
        if (!cancelled) {
          setRenewal(result);
        }
      } catch {
        if (!cancelled) {
          setRenewal(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading || !renewal?.eligible) {
    return null;
  }

  const expiryLabel = formatExpiry(renewal.expires_at);
  const priceLabel = formatCurrency(renewal.price_cents ?? 0);
  const statusText = renewal.expired
    ? expiryLabel
      ? `Expired ${expiryLabel}`
      : "Expired"
    : renewal.days_left != null && renewal.days_left <= 7
      ? expiryLabel
        ? `Expires ${expiryLabel} (${renewal.days_left} day${renewal.days_left === 1 ? "" : "s"} left)`
        : "Expiring soon"
      : expiryLabel
        ? `Renews ${expiryLabel}`
        : "Active plan";

  async function onRenew() {
    setPurchasing(true);
    setError(null);
    try {
      const payment: BillingPayment = await createQuotaRenewal();
      if (payment.checkout_url) {
        window.location.href = payment.checkout_url;
        return;
      }
      setError("Checkout could not be started. Please try again.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start renewal.");
    } finally {
      setPurchasing(false);
    }
  }

  return (
    <Card className="rounded-[28px] border-violet-400/25 bg-[linear-gradient(135deg,rgba(76,29,149,0.35),rgba(10,14,34,0.98))] shadow-[0_24px_80px_rgba(33,16,64,0.28)]">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="rounded-full bg-gradient-to-br from-[#7466F1] to-[#A259FF] p-2">
            <RefreshCw className="h-5 w-5 text-white" />
          </div>
          <div>
            <CardTitle className="font-display text-2xl text-white">
              {renewal.plan_name ?? "Your plan"}
            </CardTitle>
            <CardDescription className="text-slate-300/80">{statusText}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4">
        <p className="text-sm text-slate-300/80">
          Auto-renew this plan for one more month ({renewal.billing_cycle_days ?? 30} days) to keep
          your credits and desktop studio access active. Video export and merge are always free.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            disabled={purchasing}
            onClick={() => void onRenew()}
            className="h-11 bg-gradient-to-r from-[#7466F1] to-[#A259FF] text-white hover:from-[#6558e6] hover:to-[#9147ef]"
          >
            {purchasing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Auto-renew for {priceLabel}
          </Button>
          <span className="text-xs text-slate-400">
            {renewal.expired
              ? "Your plan has ended — renew now to restore access."
              : "Secure KHQR checkout via CutLuy — one payment renews one month."}
          </span>
        </div>
        {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      </CardContent>
    </Card>
  );
}
