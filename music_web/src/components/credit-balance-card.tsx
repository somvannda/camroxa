'use client';

import { useState, useEffect } from 'react';
import { Coins, TrendingUp, Loader2, Plus } from 'lucide-react';
import { fetchCreditBalance, creditsToSongs, type CreditBalance } from '@/lib/subscription-api';
import TopupModal from '@/components/topup-modal';

export default function CreditBalanceCard() {
  const [balance, setBalance] = useState<CreditBalance | null>(null);
  const [loading, setLoading] = useState(true);
  const [showTopupModal, setShowTopupModal] = useState(false);

  useEffect(() => {
    loadBalance();
  }, []);

  async function loadBalance() {
    try {
      const data = await fetchCreditBalance();
      setBalance(data);
    } catch (err) {
      console.error('Failed to load credit balance:', err);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-3xl border border-white/8 bg-[rgba(8,10,20,0.55)] p-8 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
      </div>
    );
  }

  if (!balance) {
    return (
      <div className="rounded-3xl border border-white/8 bg-[rgba(8,10,20,0.55)] p-8">
        <p className="text-slate-400 text-center">No credit information available</p>
      </div>
    );
  }

  const totalSongs = creditsToSongs(balance.total_credits);
  const monthlySongs = creditsToSongs(balance.monthly_credits - balance.monthly_credits_used);
  const topupSongs = creditsToSongs(balance.topup_credits);
  const dailyRemaining = Math.max(0, balance.daily_free_limit - balance.daily_free_used);
  const isFreePlan = !balance.has_subscription;

  return (
    <>
      <div className="rounded-3xl border border-purple-500/20 bg-gradient-to-br from-purple-900/20 via-[rgba(8,10,20,0.55)] to-transparent p-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-full bg-purple-500/20">
              <Coins className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="font-display text-xl font-semibold text-white">Credit Balance</h2>
              <p className="text-xs text-slate-400">
                {isFreePlan ? 'Daily free credits for music creation' : 'Available for music creation'}
              </p>
            </div>
          </div>
        </div>

        <div className="mb-6 pb-6 border-b border-white/10">
          <div className="flex items-baseline gap-2">
            <span className="text-5xl font-bold text-white">
              {isFreePlan ? dailyRemaining : totalSongs}
            </span>
            <span className="text-lg text-slate-400">
              {isFreePlan ? 'credits left today' : 'songs'}
            </span>
          </div>
          <div className="text-sm text-slate-500 mt-1">
            {isFreePlan
              ? `${dailyRemaining} / ${balance.daily_free_limit} daily free credits`
              : `${balance.total_credits.toLocaleString()} credits total`}
          </div>
        </div>

        {isFreePlan ? (
          <div className="rounded-xl border border-violet-500/20 bg-violet-500/10 p-4 text-sm text-slate-300">
            You&apos;re on the <span className="text-white">Free</span> plan. Upgrade for more daily
            credits, downloads, and commercial usage.
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="w-4 h-4 text-purple-400" />
                  <span className="text-xs text-purple-300 font-medium">Monthly</span>
                </div>
                <div className="text-2xl font-bold text-white">{monthlySongs}</div>
                <div className="text-xs text-slate-400 mt-1">
                  {balance.monthly_credits - balance.monthly_credits_used} / {balance.monthly_credits} credits
                </div>
                <div className="text-xs text-slate-500 mt-1">Resets monthly</div>
              </div>

              <div className="p-4 rounded-xl bg-pink-500/10 border border-pink-500/20">
                <div className="flex items-center gap-2 mb-2">
                  <Plus className="w-4 h-4 text-pink-400" />
                  <span className="text-xs text-pink-300 font-medium">Top-ups</span>
                </div>
                <div className="text-2xl font-bold text-white">{topupSongs}</div>
                <div className="text-xs text-slate-400 mt-1">
                  {balance.topup_credits} credits
                </div>
                <div className="text-xs text-slate-500 mt-1">Never expire</div>
              </div>
            </div>

            <button
              onClick={() => setShowTopupModal(true)}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white font-medium transition-all flex items-center justify-center gap-2"
            >
              <Plus className="w-5 h-5" />
              <span>Buy More Credits</span>
            </button>
          </>
        )}
      </div>

      {/* Top-up Modal */}
      <TopupModal isOpen={showTopupModal} onClose={() => setShowTopupModal(false)} />
    </>
  );
}
