'use client';

import { useEffect, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';

import {
  fetchQuotaRenewal,
  formatPrice,
  purchaseQuotaRenewal,
  type QuotaRenewal,
} from '@/lib/subscription-api';
import CutluyCheckoutModal from '@/components/cutluy-checkout-modal';

function formatExpiry(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return null;
  return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}

export default function QuotaRenewalCard() {
  const [renewal, setRenewal] = useState<QuotaRenewal | null>(null);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [qrString, setQrString] = useState<string | null>(null);
  const [paymentId, setPaymentId] = useState<string | null>(null);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setRenewal(await fetchQuotaRenewal());
    } catch {
      setRenewal(null);
    } finally {
      setLoading(false);
    }
  }

  if (loading || !renewal?.eligible) return null;

  const expiryLabel = formatExpiry(renewal.expires_at);
  const priceLabel = formatPrice(renewal.price_cents ?? 0);

  async function onRenew() {
    setPurchasing(true);
    setError(null);
    try {
      const result = await purchaseQuotaRenewal();
      setCheckoutUrl(result.checkout_url);
      setPaymentId(result.payment_id);
      setQrString(result.qr_string || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to start renewal.');
    } finally {
      setPurchasing(false);
    }
  }

  function closeCheckout() {
    setCheckoutUrl(null);
    setQrString(null);
    setPaymentId(null);
    setPurchasing(false);
    void load();
  }

  return (
    <>
      <div className="rounded-3xl border border-purple-500/20 bg-gradient-to-br from-purple-900/20 via-[rgba(8,10,20,0.55)] to-transparent p-8">
        <div className="mb-4 flex items-center gap-3">
          <div className="rounded-full bg-gradient-to-br from-purple-500 to-pink-500 p-2">
            <RefreshCw className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="font-display text-xl font-semibold text-white">
              {renewal.plan_name ?? 'Your plan'}
            </h2>
            <p className="text-xs text-slate-400">
              {expiryLabel ? `Renews ${expiryLabel}` : 'Desktop quota plan'}
            </p>
          </div>
        </div>

        <p className="mb-5 text-sm text-slate-400">
          Renew your plan for one more month to keep your quota active.
        </p>

        <button
          type="button"
          disabled={purchasing}
          onClick={() => void onRenew()}
          className="inline-flex h-11 items-center gap-2 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 px-6 text-sm font-medium text-white transition-all hover:from-purple-600 hover:to-pink-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {purchasing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Renew for {priceLabel}
        </button>

        {error ? <p className="mt-3 text-sm text-rose-300">{error}</p> : null}
      </div>

      <CutluyCheckoutModal
        isOpen={Boolean(checkoutUrl)}
        checkoutUrl={checkoutUrl}
        qrString={qrString}
        paymentId={paymentId}
        kind="renewal"
        planName={renewal.plan_name}
        planPrice={priceLabel}
        paidHref="/profile"
        onClose={closeCheckout}
      />
    </>
  );
}
