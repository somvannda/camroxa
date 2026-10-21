'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Sparkles, Loader2, Gift } from 'lucide-react';
import {
  fetchCreditPacks,
  purchaseTopup,
  formatPrice,
  type CreditPack,
} from '@/lib/subscription-api';
import CutluyCheckoutModal from '@/components/cutluy-checkout-modal';
import { useAuth } from '@/components/auth-provider';

/**
 * Packs-only pricing page.
 *
 * Subscriptions were retired on music.camxora.com, so this page no longer has a
 * Monthly/Yearly toggle or plan cards. It sells credit packs: one-time purchases
 * that are valid for 30 days and can be repeated any time the balance runs low.
 */
export default function PricingPageClient() {
  const router = useRouter();
  const { user } = useAuth();
  const [packs, setPacks] = useState<CreditPack[]>([]);
  const [loading, setLoading] = useState(true);
  const [purchasingPackId, setPurchasingPackId] = useState<string | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [checkoutQrString, setCheckoutQrString] = useState<string | null>(null);
  const [checkoutPaymentId, setCheckoutPaymentId] = useState<string | null>(null);
  const [checkoutPack, setCheckoutPack] = useState<{ name: string; price: string } | null>(null);

  useEffect(() => {
    loadPacks();
  }, []);

  async function loadPacks() {
    try {
      const { packs: allPacks } = await fetchCreditPacks();
      setPacks([...allPacks].sort((a, b) => a.display_order - b.display_order));
    } catch (err) {
      console.error('Failed to load credit packs:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectPack(pack: CreditPack) {
    if (!user) {
      router.push(`/login?next=/pricing`);
      return;
    }

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
    } catch (err: any) {
      console.error('Purchase failed:', err);
      alert(err.message || 'Failed to start checkout process');
      setPurchasingPackId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-b from-[#0a0e27] to-[#1a1f3a]">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
      </div>
    );
  }

  return (
    <>
      <div className="min-h-screen bg-gradient-to-b from-[#0a0e27] to-[#1a1f3a] text-white">
        {/* Header */}
        <div className="container mx-auto px-4 py-16 text-center">
          <h1 className="text-5xl font-display font-bold mb-4 bg-gradient-to-r from-purple-400 via-pink-400 to-purple-600 bg-clip-text text-transparent">
            Buy Credits
          </h1>
          <p className="text-xl text-gray-300 mb-4 max-w-2xl mx-auto">
            One-time packs of credits. No subscription, no commitment.
          </p>
          <p className="text-sm text-gray-400 max-w-2xl mx-auto">
            Your credits stay valid for 30 days from your last purchase, and buying again resets the
            clock on your whole balance. Run out early? Just buy another pack.
          </p>
        </div>

        {/* Packs */}
        <div className="container mx-auto px-4 pb-20">
          <div className="grid max-w-7xl grid-cols-1 gap-4 mx-auto md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 lg:gap-5">
            {/* Free tier — kept as the signup allowance */}
            <div className="relative rounded-2xl border-2 border-purple-500/20 bg-[#0c1230] p-5 md:p-6">
              <div className="mb-4 flex justify-center">
                <div className="rounded-full bg-purple-500/20 p-3">
                  <Gift className="h-6 w-6 text-purple-400" />
                </div>
              </div>
              <h3 className="mb-2 text-center font-display text-xl font-bold">Free</h3>
              <div className="mb-6 text-center">
                <div className="flex items-baseline justify-center gap-1">
                  <span className="text-3xl font-bold">$0</span>
                  <span className="text-gray-400">/month</span>
                </div>
              </div>
              <div className="mb-6 border-b border-purple-500/20 pb-6 text-center">
                <div className="text-2xl font-bold text-purple-400">50</div>
                <div className="text-sm text-gray-400">credits per month</div>
                <div className="mt-1 text-xs text-gray-500">Resets each month</div>
              </div>
              <ul className="mb-8 space-y-3">
                {['Web Create', 'Monthly credit reset', 'Buy packs any time'].map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <Check className="mt-0.5 h-5 w-5 flex-shrink-0 text-purple-400" />
                    <span className="text-sm text-gray-300">{feature}</span>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                onClick={() => {
                  if (!user) {
                    router.push('/register');
                    return;
                  }
                  router.push('/create');
                }}
                className="w-full rounded-lg border border-purple-500/30 bg-purple-500/20 py-3 font-medium text-purple-300 transition-all hover:bg-purple-500/30"
              >
                {user ? 'Current plan' : 'Sign up free'}
              </button>
            </div>

            {packs.map((pack, index) => {
              const isPopular = index === packs.length - 1;

              return (
                <div
                  key={pack.id}
                  className={`relative rounded-2xl border-2 p-5 transition-all md:p-6 ${
                    isPopular
                      ? 'border-purple-500 bg-gradient-to-b from-purple-900/30 to-[#0c1230] shadow-xl shadow-purple-500/20'
                      : 'border-purple-500/20 bg-[#0c1230] hover:border-purple-500/40'
                  }`}
                >
                  {isPopular && (
                    <div className="absolute -top-4 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-gradient-to-r from-purple-500 to-pink-500 px-3 py-1 text-sm font-medium">
                      Best value
                    </div>
                  )}

                  <div className="flex justify-center mb-4">
                    <div
                      className={`p-3 rounded-full ${
                        isPopular
                          ? 'bg-gradient-to-br from-purple-500 to-pink-500'
                          : 'bg-purple-500/20'
                      }`}
                    >
                      <Sparkles className={`w-6 h-6 ${isPopular ? 'text-white' : 'text-purple-400'}`} />
                    </div>
                  </div>

                  <h3 className="text-xl font-display font-bold text-center mb-2">{pack.name}</h3>

                  <div className="text-center mb-6">
                    <div className="flex items-baseline justify-center gap-1">
                      <span className="text-3xl font-bold">{formatPrice(pack.price_cents)}</span>
                      <span className="text-gray-400">one-time</span>
                    </div>
                  </div>

                  <div className="text-center mb-6 pb-6 border-b border-purple-500/20">
                    <div className="text-2xl font-bold text-purple-400">
                      {pack.total_credits.toLocaleString()}
                    </div>
                    <div className="text-sm text-gray-400">credits</div>
                    <div className="mt-1 text-xs text-gray-500">
                      ≈ {pack.songs_equivalent.toLocaleString()} songs
                    </div>
                  </div>

                  <ul className="space-y-3 mb-8">
                    {[
                      'Valid for 30 days from purchase',
                      'Buy again any time',
                      'Instant delivery after payment',
                    ].map((feature) => (
                      <li key={feature} className="flex items-start gap-3">
                        <Check className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
                        <span className="text-sm text-gray-300">{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <button
                    onClick={() => handleSelectPack(pack)}
                    disabled={purchasingPackId === pack.id}
                    className={`w-full py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${
                      isPopular
                        ? 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white'
                        : 'bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/30'
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                  >
                    {purchasingPackId === pack.id ? (
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

          {/* FAQ / Info */}
          <div className="max-w-3xl mx-auto mt-16 text-center text-gray-400 text-sm space-y-2">
            <p>All purchases are securely processed via KHQR</p>
            <p>Credits are valid for 30 days from your last purchase — buying again extends them</p>
            <p>No subscription • No auto-renewal • Buy only when you need credits</p>
          </div>
        </div>
      </div>
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
