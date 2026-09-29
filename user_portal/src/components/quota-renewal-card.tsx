"use client";

import * as React from "react";
import { Loader2, RefreshCw, X } from "lucide-react";

import {
  createQuotaRenewal,
  getBillingPayment,
  getQuotaRenewal,
  type QuotaRenewal,
} from "@/lib/billing";

function formatMoney(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

function formatExpiry(value?: string | null): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

type Checkout = {
  paymentId: string;
  qrPayload: string;
  checkoutUrl: string;
};

export default function QuotaRenewalCard() {
  const [renewal, setRenewal] = React.useState<QuotaRenewal | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [starting, setStarting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [checkout, setCheckout] = React.useState<Checkout | null>(null);
  const [paid, setPaid] = React.useState(false);

  async function load() {
    setLoading(true);
    try {
      setRenewal(await getQuotaRenewal());
    } catch {
      setRenewal(null);
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    void load();
  }, []);

  React.useEffect(() => {
    if (!checkout || paid) return;
    const current = checkout;
    let cancelled = false;

    async function poll() {
      while (!cancelled) {
        try {
          const p = await getBillingPayment(current.paymentId);
          if (p.status === "paid") {
            setPaid(true);
            return;
          }
          if (p.status === "failed" || p.status === "expired") {
            setError("Payment was not completed. Please try again.");
            return;
          }
        } catch {
          // keep polling
        }
        await new Promise((r) => setTimeout(r, 2000));
      }
    }

    void poll();
    return () => {
      cancelled = true;
    };
  }, [checkout, paid]);

  if (loading || !renewal?.eligible) return null;

  const canRenew = renewal.renewable !== false;
  const expiryLabel = formatExpiry(renewal.expires_at);
  const priceLabel = formatMoney(renewal.price_cents ?? 0);
  const expiryDate = renewal.expires_at ? new Date(renewal.expires_at) : null;
  const daysLeft =
    expiryDate && !Number.isNaN(expiryDate.getTime())
      ? Math.ceil((expiryDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
      : null;
  const isExpired = daysLeft != null && daysLeft <= 0;
  const isSoon = daysLeft != null && daysLeft > 0 && daysLeft <= 7;
  const badge = isExpired
    ? { label: `Expired ${Math.abs(daysLeft ?? 0)}d ago`, cls: "text-red-300 border-red-500/20 bg-red-500/10" }
    : isSoon
      ? { label: `Expires in ${daysLeft ?? 0}d`, cls: "text-yellow-300 border-yellow-500/20 bg-yellow-500/10" }
      : { label: `${daysLeft ?? ""}d left`, cls: "text-emerald-300 border-emerald-500/20 bg-emerald-500/10" };

  async function onRenew() {
    setStarting(true);
    setError(null);
    setPaid(false);
    try {
      const result = await createQuotaRenewal();
      const qrPayload =
        result.qr_string && result.qr_string.startsWith("000201")
          ? result.qr_string
          : result.checkout_url;
      setCheckout({ paymentId: result.id, qrPayload, checkoutUrl: result.checkout_url });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to start renewal.");
    } finally {
      setStarting(false);
    }
  }

  function closeCheckout() {
    setCheckout(null);
    setPaid(false);
    setError(null);
    void load();
  }

  return (
    <>
      <div className="rounded-[24px] border border-violet-400/25 bg-[linear-gradient(135deg,rgba(116,102,241,0.16),rgba(9,12,28,0.98))] p-6 shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 p-2">
              <RefreshCw className="h-5 w-5 text-white" />
            </div>
            <div>
              <div className="font-display text-lg font-semibold text-white">
                {renewal.plan_name ?? "Your plan"}
              </div>
              <div className="text-sm text-slate-300/72">
                {expiryLabel ? `Renews ${expiryLabel}` : "Desktop quota plan"}
              </div>
            </div>
          </div>
          <span className={`rounded-full border px-3 py-1 text-[11px] uppercase tracking-wide ${badge.cls}`}>
            {badge.label}
          </span>
        </div>

        <p className="mb-5 text-sm text-slate-300/72">
          {canRenew ? (
            <>
              Auto-renew an extra {renewal.billing_cycle_days ?? 30} days — added on top of your
              current expiry, so you never lose remaining days. Video export and merge stay free.
            </>
          ) : (
            <>
              Renewal opens {renewal.renewal_window_days ?? 7} days before your plan ends —{" "}
              {renewal.renewal_opens_in_days ?? 0} day
              {(renewal.renewal_opens_in_days ?? 0) === 1 ? "" : "s"} to go. Video export and merge
              stay free.
            </>
          )}
        </p>

        <button
          type="button"
          disabled={starting || !canRenew}
          onClick={() => void onRenew()}
          className="inline-flex h-11 items-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 px-6 text-sm font-medium text-white transition hover:from-violet-600 hover:to-fuchsia-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          {canRenew ? `Auto-renew for ${priceLabel}` : `Renewal opens in ${renewal.renewal_opens_in_days ?? 0}d`}
        </button>

        {error ? <p className="mt-3 text-sm text-red-300">{error}</p> : null}
      </div>

      {checkout ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[24px] border border-white/10 bg-[linear-gradient(180deg,rgba(18,28,70,0.98),rgba(9,12,28,0.98))] p-6 shadow-[0_24px_80px_rgba(18,24,58,0.5)]">
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h2 className="font-display text-xl font-semibold text-white">
                  {paid ? "Renewal complete" : "Complete payment with KHQR"}
                </h2>
                <p className="mt-1 text-sm text-slate-300/72">
                  {paid
                    ? "Your plan has been renewed for another period."
                    : `Scan the KHQR code below with Bakong or your bank app.`}
                </p>
              </div>
              <button
                type="button"
                onClick={closeCheckout}
                className="shrink-0 rounded-full p-2 text-slate-400 transition hover:bg-white/10 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {paid ? (
              <div className="flex flex-col items-center gap-4 py-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300">
                  <RefreshCw className="h-6 w-6" />
                </div>
                <button
                  type="button"
                  onClick={closeCheckout}
                  className="h-11 w-full rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 text-sm font-medium text-white"
                >
                  Done
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4">
                <div className="flex items-center justify-center rounded-2xl bg-white p-4">
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(checkout.qrPayload)}`}
                    alt="KHQR payment code"
                    width={220}
                    height={220}
                    className="h-[220px] w-[220px]"
                  />
                </div>
                <a
                  href={checkout.checkoutUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-violet-300 underline underline-offset-2 hover:text-violet-200"
                >
                  Open full checkout page
                </a>
                <p className="text-xs text-slate-500">Payment is confirmed automatically after you pay.</p>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </>
  );
}
