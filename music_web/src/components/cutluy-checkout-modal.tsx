'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/navigation';
import { Check, ExternalLink, Loader2, QrCode, X } from 'lucide-react';
import {
  fetchSubscriptionCheckoutStatus,
  fetchTopupCheckoutStatus,
  formatPlanDisplayName,
  isAllowedCutluyCheckoutUrl,
  type CheckoutStatus,
} from '@/lib/subscription-api';
import KhqrCode from '@/components/khqr-code';

type CutluyCheckoutModalProps = {
  isOpen: boolean;
  checkoutUrl: string | null;
  qrString?: string | null;
  paymentId?: string | null;
  kind?: 'subscription' | 'topup';
  title?: string;
  planName?: string;
  planPrice?: string;
  onClose: () => void;
};

export default function CutluyCheckoutModal({
  isOpen,
  checkoutUrl,
  qrString,
  paymentId,
  kind = 'subscription',
  title = 'Complete payment with KHQR',
  planName,
  planPrice,
  onClose,
}: CutluyCheckoutModalProps) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [status, setStatus] = useState<CheckoutStatus | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!isOpen || !paymentId) {
      setStatus(null);
      setPollError(null);
      return;
    }

    let cancelled = false;
    const poll = async () => {
      try {
        const next =
          kind === 'topup'
            ? await fetchTopupCheckoutStatus(paymentId)
            : await fetchSubscriptionCheckoutStatus(paymentId);
        if (cancelled) return;
        setStatus(next);
        setPollError(null);
        if (next.status === 'paid' && next.fulfilled) {
          window.dispatchEvent(new Event('camxora:credits-updated'));
        }
      } catch (err) {
        if (cancelled) return;
        setPollError(err instanceof Error ? err.message : 'Unable to check payment status.');
      }
    };

    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [isOpen, paymentId, kind]);

  const safeCheckoutUrl = isAllowedCutluyCheckoutUrl(checkoutUrl) ? checkoutUrl : null;
  const khqrPayload = qrString?.startsWith('000201') ? qrString : null;

  if (!mounted || !isOpen || !checkoutUrl) return null;

  const paid = status?.status === 'paid' && status.fulfilled;
  const failed = status?.status === 'failed' || status?.status === 'expired';
  const rawName = status?.plan_name || status?.pack_name || planName || 'your purchase';
  const displayName =
    kind === 'topup' || status?.pack_name
      ? rawName
      : formatPlanDisplayName(rawName);
  const credits = status?.credits ?? 0;

  const goToCreate = () => {
    onClose();
    router.push('/create');
  };

  const heading = paid
    ? 'Payment successful'
    : failed
      ? status?.status === 'expired'
        ? 'Payment expired'
        : 'Payment failed'
      : planName
        ? `Pay for ${planName}`
        : title;

  const modal = (
    <div
      className="fixed inset-0 z-[220] flex items-center justify-center bg-black/80 p-3 backdrop-blur-sm sm:p-4"
      onClick={paid ? goToCreate : onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="cutluy-checkout-title"
    >
      <div
        className="relative flex w-full max-w-[360px] flex-col overflow-hidden rounded-3xl border border-white/10 bg-slate-900 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-white/10 px-4 py-3 sm:px-5 sm:py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              {paid ? (
                <Check className="h-5 w-5 shrink-0 text-emerald-300" />
              ) : (
                <QrCode className="h-5 w-5 shrink-0 text-fuchsia-300" />
              )}
              <h2 id="cutluy-checkout-title" className="truncate text-base font-semibold text-white sm:text-lg">
                {heading}
              </h2>
            </div>
            {paid ? (
              <p className="mt-1 pl-7 text-sm text-slate-400">Credits are now on your account.</p>
            ) : failed ? (
              <p className="mt-1 pl-7 text-sm text-slate-400">No credits were added. You can try again from Create.</p>
            ) : planPrice ? (
              <p className="mt-1 pl-7 text-sm text-slate-400">
                {planPrice} · Scan the KHQR code below
              </p>
            ) : (
              <p className="mt-1 pl-7 text-sm text-slate-400">Scan the KHQR code below</p>
            )}
          </div>
          <button
            type="button"
            onClick={paid ? goToCreate : onClose}
            className="shrink-0 rounded-full p-2 text-slate-400 transition hover:bg-white/10 hover:text-white"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {paid ? (
          <div className="space-y-4 px-5 py-6 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/15">
              <Check className="h-7 w-7 text-emerald-300" />
            </div>
            <div>
              <p className="text-lg font-semibold text-white">{displayName}</p>
              <p className="mt-1 text-sm text-slate-400">
                {credits > 0 ? `${credits.toLocaleString()} credits added` : 'Your purchase is active.'}
              </p>
            </div>
            <button
              type="button"
              onClick={goToCreate}
              className="flex h-12 w-full items-center justify-center rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 text-sm font-medium text-white"
            >
              Close
            </button>
          </div>
        ) : failed ? (
          <div className="space-y-4 px-5 py-6 text-center">
            <p className="text-sm text-slate-300">
              {status?.status === 'expired'
                ? 'This KHQR code expired before payment completed.'
                : 'CutLuy could not confirm this payment.'}
            </p>
            <button
              type="button"
              onClick={onClose}
              className="flex h-12 w-full items-center justify-center rounded-xl bg-white/10 text-sm font-medium text-white hover:bg-white/20"
            >
              Close
            </button>
          </div>
        ) : (
          <>
            <div className="bg-white/[0.02] px-4 py-3 sm:px-5">
              {khqrPayload ? (
                <div className="mx-auto w-full max-w-[280px]">
                  <KhqrCode value={khqrPayload} size={232} />
                </div>
              ) : (
                <p className="px-2 py-6 text-center text-sm text-slate-300">
                  CutLuy does not allow this page inside our app. Open the full checkout to scan KHQR.
                </p>
              )}
              {safeCheckoutUrl ? (
                <div className="mt-3 flex items-center justify-between gap-3 text-xs sm:text-sm">
                  <p className="text-slate-400">
                    {khqrPayload ? 'Scan with Bakong or your bank app' : 'Secure payment via CutLuy'}
                  </p>
                  <a
                    href={safeCheckoutUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex shrink-0 items-center gap-1 text-fuchsia-200 hover:text-white"
                  >
                    Open full page
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>
              ) : (
                <p className="px-2 py-8 text-center text-sm text-slate-300">
                  Checkout URL was rejected. Close and try again.
                </p>
              )}
            </div>
            <div className="border-t border-white/10 px-4 py-3 text-center sm:px-5">
              <div className="inline-flex items-center gap-2 text-xs text-slate-400 sm:text-sm">
                <Loader2 className="h-4 w-4 animate-spin text-violet-400" />
                {pollError ? pollError : 'Waiting for payment confirmation…'}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
