'use client';

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, Sparkles, Loader2, Check } from 'lucide-react';
import CutluyCheckoutModal from '@/components/cutluy-checkout-modal';
import {
  fetchCreditPacks,
  purchaseTopup,
  formatPrice,
  packBonusPercent,
  type CreditPack,
} from '@/lib/subscription-api';

interface TopupModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function TopupModal({ isOpen, onClose }: TopupModalProps) {
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
              <h2 className="text-2xl font-display font-bold text-white">Buy Credit Top-up</h2>
              <p className="text-sm text-slate-400">One-time purchase • Credits never expire</p>
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
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {packs.map((pack, index) => {
                const isPurchasing = purchasingPackId === pack.id;
                const isPopular = index === 1; // Balanced $10 pack is the recommended pick
                const bonus = packBonusPercent(pack);
                const baseCredits = Math.round((pack.price_cents / 100) * 350);

                return (
                  <div
                    key={pack.id}
                    className={`relative rounded-xl p-6 border-2 transition-all hover:scale-[1.02] ${
                      isPopular
                        ? 'border-purple-500 bg-gradient-to-br from-purple-900/30 to-[#0c1230]/50'
                        : 'border-purple-500/20 bg-[#0c1230]/50 hover:border-purple-500/40'
                    }`}
                  >
                    {isPopular && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full text-xs font-medium">
                        Recommended
                      </div>
                    )}

                    {/* Volume bonus */}
                    {bonus > 0 && (
                      <div className="absolute right-4 top-4 rounded-full bg-green-500/15 px-2.5 py-1 text-xs font-semibold text-green-400">
                        +{bonus}% bonus
                      </div>
                    )}

                    {/* Pack Name & Icon */}
                    <div className="flex items-center gap-3 mb-4">
                      <div
                        className={`p-2 rounded-full ${
                          isPopular
                            ? 'bg-gradient-to-br from-purple-500 to-pink-500'
                            : 'bg-purple-500/20'
                        }`}
                      >
                        <Sparkles className={`w-4 h-4 ${isPopular ? 'text-white' : 'text-purple-400'}`} />
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-white">{pack.name}</h3>
                        <p className="text-xs text-slate-400">{pack.description}</p>
                      </div>
                    </div>

                    {/* Credits & Price */}
                    <div className="mb-4 pb-4 border-b border-white/10">
                      <div className="flex items-baseline justify-between mb-2">
                        <div>
                          <div className="text-3xl font-bold text-purple-400">
                            {pack.songs_equivalent}
                          </div>
                          <div className="text-xs text-slate-400">songs</div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-white">
                            {formatPrice(pack.price_cents)}
                          </div>
                          <div className="text-xs text-slate-400">one-time</div>
                        </div>
                      </div>
                      <div className="text-xs text-slate-500">
                        {pack.total_credits.toLocaleString()} credits
                        {bonus > 0
                          ? ` (${baseCredits.toLocaleString()} + ${(pack.total_credits - baseCredits).toLocaleString()} bonus)`
                          : ''}{' '}
                        • Never expire
                      </div>
                    </div>

                    {/* Features */}
                    <ul className="space-y-2 mb-4">
                      <li className="flex items-start gap-2 text-sm text-slate-300">
                        <Check className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
                        <span>Credits added to your account instantly</span>
                      </li>
                      <li className="flex items-start gap-2 text-sm text-slate-300">
                        <Check className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
                        <span>Never expire or reset</span>
                      </li>
                      <li className="flex items-start gap-2 text-sm text-slate-300">
                        <Check className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
                        <span>Use after monthly credits</span>
                      </li>
                    </ul>

                    {/* Purchase Button */}
                    <button
                      onClick={() => handlePurchase(pack)}
                      disabled={isPurchasing}
                      className={`w-full py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${
                        isPopular
                          ? 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white'
                          : 'bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/30'
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {isPurchasing ? (
                        <>
                          <Loader2 className="w-5 h-5 animate-spin" />
                          <span>Processing...</span>
                        </>
                      ) : (
                        <span>Buy {pack.name}</span>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Info */}
          <div className="mt-6 p-4 rounded-xl bg-purple-500/10 border border-purple-500/20">
            <div className="flex items-start gap-3">
              <div className="p-1.5 rounded-full bg-purple-500/20">
                <Sparkles className="w-4 h-4 text-purple-400" />
              </div>
              <div className="text-sm text-slate-300">
                <div className="font-medium mb-1">How top-up credits work:</div>
                <ul className="space-y-1 text-slate-400 text-xs">
                  <li>• Top-up credits never expire and carry over indefinitely</li>
                  <li>• They're used after your monthly subscription credits run out</li>
                  <li>• Perfect for busy months or special projects</li>
                  <li>• Instant delivery after payment confirmation</li>
                </ul>
              </div>
            </div>
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
        title="Top up with KHQR"
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
