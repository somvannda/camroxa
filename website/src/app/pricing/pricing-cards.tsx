import { Check, Gift, Sparkles } from "lucide-react";

import { formatMusicWebPrice } from "@/lib/credits-only-public";

export type CreditPack = {
  id: string;
  slug: string;
  name: string;
  description?: string;
  total_credits: number;
  price_cents: number;
  display_order: number;
  songs_equivalent: number;
};

/**
 * Packs-only pricing cards.
 *
 * Subscriptions are retired on music.camxora.com, so there is no monthly/yearly
 * toggle and no plan families. Purchases happen in the music web app; this page
 * only advertises the ladder.
 */
export function PricingCards({
  packs,
  musicWebBaseUrl,
}: {
  packs: CreditPack[];
  musicWebBaseUrl: string;
}) {
  const sorted = [...packs].sort((a, b) => a.display_order - b.display_order);
  const signupHref = `${musicWebBaseUrl}/register`;
  const checkoutHref = `${musicWebBaseUrl}/pricing`;

  return (
    <div className="text-white">
      <div className="mb-10 text-center">
        <h1 className="mb-4 bg-gradient-to-r from-purple-400 via-pink-400 to-purple-600 bg-clip-text font-display text-5xl font-bold text-transparent">
          Buy Credits
        </h1>
        <p className="mx-auto mb-4 max-w-2xl text-xl text-gray-300">
          One-time packs of credits. No subscription, no commitment.
        </p>
        <p className="mx-auto max-w-2xl text-sm text-gray-400">
          Credits stay valid for 30 days from your last purchase, and buying again resets the clock
          on your whole balance. Run out early? Just buy another pack.
        </p>
      </div>

      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-5">
        {/* Free tier. 50 credits/month is seeded by platform_api migration 130 and
            guarded by migration 132 (a plan grants either daily or monthly). */}
        <article className="relative rounded-2xl border-2 border-purple-500/20 bg-[#0c1230] p-6 md:p-8">
          <div className="mb-4 flex justify-center">
            <div className="rounded-full bg-purple-500/20 p-3">
              <Gift className="h-6 w-6 text-purple-400" />
            </div>
          </div>
          <h3 className="mb-2 text-center font-display text-2xl font-bold">Free</h3>
          <div className="mb-6 text-center">
            <div className="flex items-baseline justify-center gap-1">
              <span className="text-4xl font-bold">$0</span>
              <span className="text-gray-400">/month</span>
            </div>
          </div>
          <div className="mb-6 border-b border-purple-500/20 pb-6 text-center">
            <div className="text-3xl font-bold text-purple-400">50</div>
            <div className="text-sm text-gray-400">credits per month</div>
            <div className="mt-1 text-xs text-gray-500">Resets each month</div>
          </div>
          <ul className="mb-8 space-y-3">
            {["Web Create", "Monthly credit reset", "Buy packs any time"].map((feature) => (
              <li key={feature} className="flex items-start gap-3">
                <Check className="mt-0.5 h-5 w-5 flex-shrink-0 text-purple-400" />
                <span className="text-sm text-gray-300">{feature}</span>
              </li>
            ))}
          </ul>
          <a
            href={signupHref}
            className="block w-full rounded-lg border border-purple-500/30 bg-purple-500/20 py-3 text-center font-medium text-purple-300 transition-all hover:bg-purple-500/30"
          >
            Sign up free
          </a>
        </article>

        {sorted.map((pack, index) => {
          const isPopular = index === sorted.length - 1;

          return (
            <article
              key={pack.id}
              className={`relative rounded-2xl border-2 p-6 transition-all md:p-8 ${
                isPopular
                  ? "border-purple-500 bg-gradient-to-b from-purple-900/30 to-[#0c1230] shadow-xl shadow-purple-500/20"
                  : "border-purple-500/20 bg-[#0c1230] hover:border-purple-500/40"
              }`}
            >
              {isPopular ? (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-gradient-to-r from-purple-500 to-pink-500 px-4 py-1 text-sm font-medium">
                  Best value
                </div>
              ) : null}
              <div className="mb-4 flex justify-center">
                <div
                  className={`rounded-full p-3 ${
                    isPopular
                      ? "bg-gradient-to-br from-purple-500 to-pink-500"
                      : "bg-purple-500/20"
                  }`}
                >
                  <Sparkles className={`h-6 w-6 ${isPopular ? "text-white" : "text-purple-400"}`} />
                </div>
              </div>
              <h3 className="mb-2 text-center font-display text-2xl font-bold">{pack.name}</h3>
              <div className="mb-6 text-center">
                <div className="flex items-baseline justify-center gap-1">
                  <span className="text-4xl font-bold">
                    {formatMusicWebPrice(pack.price_cents)}
                  </span>
                  <span className="text-gray-400">one-time</span>
                </div>
              </div>
              <div className="mb-6 border-b border-purple-500/20 pb-6 text-center">
                <div className="text-3xl font-bold text-purple-400">
                  {pack.total_credits.toLocaleString()}
                </div>
                <div className="text-sm text-gray-400">credits</div>
                <div className="mt-1 text-xs text-gray-500">
                  ≈ {pack.songs_equivalent.toLocaleString()} songs
                </div>
              </div>
              <ul className="mb-8 space-y-3">
                {["Valid for 30 days from purchase", "Buy again any time", "Instant delivery"].map(
                  (feature) => (
                    <li key={feature} className="flex items-start gap-3">
                      <Check className="mt-0.5 h-5 w-5 flex-shrink-0 text-purple-400" />
                      <span className="text-sm text-gray-300">{feature}</span>
                    </li>
                  ),
                )}
              </ul>
              <a
                href={checkoutHref}
                className={`block w-full rounded-lg py-3 text-center font-medium transition-all ${
                  isPopular
                    ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600"
                    : "border border-purple-500/30 bg-purple-500/20 text-purple-300 hover:bg-purple-500/30"
                }`}
              >
                Buy {pack.name}
              </a>
            </article>
          );
        })}
      </div>

      <div className="mx-auto mt-16 max-w-3xl space-y-2 text-center text-sm text-gray-400">
        <p>💳 Secure payment processing via CutLuy</p>
        <p>⏳ Credits are valid for 30 days from your last purchase — buying again extends them</p>
        <p>✅ No subscription • No auto-renewal • Buy only when you need credits</p>
      </div>
    </div>
  );
}
