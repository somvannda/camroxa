'use client';

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Sparkles, Loader2, Check, Lock } from 'lucide-react';
import CutluyCheckoutModal from '@/components/cutluy-checkout-modal';
import {
  fetchCreditPacks,
  purchaseTopup,
  formatPrice,
  type CreditPack,
} from '@/lib/subscription-api';

interface TopupModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Optional context shown above the pack grid (e.g. a premium-model block). */
  headline?: string;
  message?: string;
}

export default function TopupModal({ isOpen, onClose, headline, message }: TopupModalProps) {
  const [mounted, setMounted] = useState(false);
  const [packs, setPacks] = useState<CreditPack[]>([]);
  const [loading, setLoading] = useState(true);
  const [purchasingPackId, setPurchasingPackId] = useState<string | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [checkoutQrString, setCheckoutQrString] = useState<string | null>(null);
  const [checkoutPaymentId, setCheckoutPaymentId] = useState<string | null>(null);
  const [checkoutPack, setCheckoutPack] = useState<{ name: string; price: string } | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadPacks();
    }
  }, [isOpen]);

  async function loadPacks() {
    try {
      const { packs: allPacks } = await fetchCreditPacks();
      setPacks(allPacks.sort((a, b) => a.display_order - b.display_order));
    } catch (err) {
      console.error('Failed to load credit packs:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handlePurchase(pack: CreditPack) {
    setPurchasingPackId(pack.id);

    try {
      const currentUrl = window.location.origin;
      const { checkout_url, payment_id, qr_string } = await purchaseTopup({
        pack_slug: pack.slug,
        success_url: `${currentUrl}/create`,
        cancel_url: `${currentUrl}/create`,
      });

      setCheckoutPack({ name: pack.name, price: formatPrice(pack.price_cents) });
      setCheckoutPaymentId(payment_id);
      setCheckoutQrString(qr_string || null);
      setCheckoutUrl(checkout_url);
      onClose();
    } catch (err: any) {
      console.error('Purchase failed:', err);
      alert(err.message || 'Failed to start checkout process');
      setPurchasingPackId(null);
    }
  }

  if (!mounted) return null;

  return (
    <>
      {isOpen
        ? createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-gradient-to-b from-[#0c1230] to-[#0a0e27] rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-purple-500/20 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-[#0c1230]/95 backdrop-blur-sm border-b border-white/10 p-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-full bg-gradient-to-br from-purple-500 to-pink-500">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-display font-bold text-white">Buy Credits</h2>
              <p className="text-sm text-slate-400">One-time purchase • Credits valid for 30 days</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {message && (
            <div className="mb-5 flex items-start gap-3 rounded-xl border border-amber-400/25 bg-amber-400/10 px-4 py-3">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-400/15 text-amber-300">
                <Lock className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-white">
                  {headline ?? 'A credit pack is required'}
                </div>
                <p className="mt-1 text-sm leading-relaxed text-amber-100/80">{message}</p>
              </div>
            </div>
          )}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
            </div>
          ) : (
            <div className="grid auto-rows-fr grid-cols-1 items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {packs.map((pack, index) => {
                const isPurchasing = purchasingPackId === pack.id;
                // The $10 pack is the recommended middle tier.
                const tenDollarIndex = packs.findIndex((item) => item.price_cents === 1000);
                const popularIndex =
                  tenDollarIndex >= 0 ? tenDollarIndex : Math.min(1, packs.length - 1);
                const isPopular = index === popularIndex;
                const base = packs[0];
                const baseRate =
                  base && base.price_cents > 0
                    ? base.total_credits / (base.price_cents / 100)
                    : 0;
                const packRate =
                  pack.price_cents > 0 ? pack.total_credits / (pack.price_cents / 100) : 0;
                const bonusPct =
                  baseRate > 0 && packRate > 0
                    ? Math.round((packRate / baseRate - 1) * 100)
                    : 0;

                return (
                  <div
                    key={pack.id}
                    className={`relative flex h-full flex-col rounded-xl border p-4 transition-colors ${
                      isPopular
                        ? 'border-purple-500 bg-gradient-to-br from-purple-900/30 to-[#0c1230]/50'
                        : 'border-purple-500/20 bg-[#0c1230]/50 hover:border-purple-500/40'
                    }`}
                  >
                    {/* Reserved badge row keeps every card's header aligned. */}
                    <div className="flex h-5 items-center justify-end">
                      {isPopular && (
                        <span className="rounded-full bg-gradient-to-r from-purple-500 to-pink-500 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                          Most popular
                        </span>
                      )}
                    </div>

                    {/* Header: fixed one-line name so every card starts the same row. */}
                    <div className="mt-1 flex min-w-0 items-center gap-2">
                      <span
                        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
                          isPopular
                            ? 'bg-gradient-to-br from-purple-500 to-pink-500'
                            : 'bg-purple-500/20'
                        }`}
                      >
                        <Sparkles
                          className={`h-3.5 w-3.5 ${isPopular ? 'text-white' : 'text-purple-400'}`}
                        />
                      </span>
                      <h3 className="truncate text-base font-semibold text-white" title={pack.name}>
                        {pack.name}
                      </h3>
                    </div>

                    {/* Primary metric row: credits (what you buy) and price. */}
                    <div className="mt-4 flex items-end justify-between gap-2 border-b border-white/10 pb-3">
                      <div className="min-w-0">
                        <div className="truncate text-2xl font-bold leading-none text-white">
                          {pack.total_credits.toLocaleString()}
                        </div>
                        <div className="mt-1 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                          credits
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <div className="text-xl font-bold leading-none text-white">
                          {formatPrice(pack.price_cents)}
                        </div>
                        <div className="mt-1 text-[10px] uppercase tracking-wider text-slate-500">
                          one-time
                        </div>
                      </div>
                    </div>

                    {/* Comparison rows: one label/value per line, identical in every card. */}
                    <dl className="mt-3 space-y-2 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <dt className="text-slate-500">Total songs</dt>
                        <dd className="font-medium text-slate-200">
                          {pack.songs_equivalent.toLocaleString()}
                        </dd>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <dt className="text-slate-500">Extra value</dt>
                        <dd
                          className={`font-semibold ${
                            bonusPct > 0 ? 'text-emerald-300' : 'text-slate-400'
                          }`}
                        >
                          {bonusPct > 0 ? `+${bonusPct}%` : 'Base'}
                        </dd>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <dt className="text-slate-500">Valid</dt>
                        <dd className="font-medium text-slate-200">30 days</dd>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <dt className="text-slate-500">Delivery</dt>
                        <dd className="font-medium text-emerald-300">Instant</dd>
                      </div>
                    </dl>

                    {/* CTA pinned to the bottom so all buttons share one baseline. */}
                    <div className="mt-auto pt-4">
                      <button
                        onClick={() => handlePurchase(pack)}
                        disabled={isPurchasing}
                        className={`w-full rounded-lg py-2.5 text-sm font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
                          isPopular
                            ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600'
                            : 'border border-purple-500/30 bg-purple-500/20 text-purple-200 hover:bg-purple-500/30'
                        }`}
                      >
                        {isPurchasing ? (
                          <span className="flex items-center justify-center gap-2">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Processing…
                          </span>
                        ) : (
                          <span>Buy {pack.name}</span>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Shared benefits: shown once instead of repeated inside every card. */}
          <div className="mt-5 rounded-xl border border-purple-500/20 bg-purple-500/10 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <Sparkles className="h-4 w-4 text-purple-400" />
              Every pack includes
            </div>
            <ul className="mt-2 grid gap-x-6 gap-y-1.5 text-xs text-slate-400 sm:grid-cols-2">
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                Credits added instantly after payment
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                Valid for 30 days from purchase
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                Buying again resets the 30-day clock
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                Buy another pack any time
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                No subscription required
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>,
    document.body,
        )
        : null}
      <CutluyCheckoutModal
        isOpen={Boolean(checkoutUrl)}
        checkoutUrl={checkoutUrl}
        qrString={checkoutQrString}
        paymentId={checkoutPaymentId}
        kind="topup"
        title="Buy credits with KHQR"
        planName={checkoutPack?.name}
        planPrice={checkoutPack?.price}
        onClose={() => {
          setCheckoutUrl(null);
          setCheckoutQrString(null);
          setCheckoutPaymentId(null);
          setCheckoutPack(null);
          setPurchasingPackId(null);
        }}
      />
    </>
  );
}
