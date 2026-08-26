import { Check } from "lucide-react";

import { formatPlanPrice, type PlanTermDiscounts } from "@/lib/plan-pricing";
import {
  cardBulletsForPlan,
  creditCaptionLines,
  creditHeadlineNumber,
  groupPublicPaidTiers,
  publicFreePlans,
  type PublicCatalogPlan,
} from "@/lib/credits-only-public";

type PublicPlanOffer = {
  id: string;
  promo_price_cents: number;
  max_redemptions: number;
  current_redemptions: number;
  remaining_redemptions: number;
  is_active: boolean;
};

export type PublicPlan = PublicCatalogPlan & {
  profile_allowance: number;
  monthly_song_limit: number | null;
  monthly_image_limit: number | null;
  monthly_draft_limit: number | null;
  monthly_video_limit: number | null;
  monthly_merge_limit: number | null;
  daily_song_limit_per_channel: number;
  daily_image_limit_per_channel: number;
  daily_draft_limit_per_channel: number;
  daily_video_limit: number;
  daily_merge_limit: number;
  included_wallet_credits: number;
  offer: PublicPlanOffer | null;
};

function CardBullets({ plan }: { plan: PublicCatalogPlan }) {
  return (
    <ul className="mb-2 space-y-2">
      {cardBulletsForPlan(plan).map((feature) => (
        <li key={feature} className="flex items-start gap-2 text-sm text-slate-200/82">
          <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-emerald-300/20 bg-emerald-400/10 text-emerald-100">
            <Check className="h-3 w-3" aria-hidden="true" />
          </span>
          <span>{feature}</span>
        </li>
      ))}
    </ul>
  );
}

function FreeCard({ plan }: { plan: PublicPlan }) {
  return (
    <article className="rounded-[28px] border border-white/10 bg-white/[0.03] p-6 ring-1 ring-white/6">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Free</div>
      <h3 className="mt-2 font-display text-2xl font-semibold text-white">Free</h3>
      <div className="mt-4 flex items-baseline gap-1">
        <span className="text-4xl font-semibold text-white">$0</span>
        <span className="text-slate-400">/month</span>
      </div>
      <div className="mt-5 border-b border-white/8 pb-5">
        <div className="text-3xl font-semibold text-emerald-200">
          {creditHeadlineNumber(plan).toLocaleString()}
        </div>
        {creditCaptionLines(plan).map((line, index) => (
          <div
            key={`${line}-${index}`}
            className={index === 0 ? "text-sm text-slate-400" : "mt-1 text-xs text-slate-500"}
          >
            {line}
          </div>
        ))}
      </div>
      <p className="mt-4 text-sm text-slate-300/75">Shown only because the Free plan is public.</p>
      <div className="mt-5">
        <CardBullets plan={plan} />
      </div>
    </article>
  );
}

export function PricingComparisonTable({
  plans,
}: {
  plans: PublicPlan[];
  termDiscounts?: PlanTermDiscounts;
}) {
  const families = groupPublicPaidTiers(plans);
  const freePlans = publicFreePlans(plans) as PublicPlan[];
  const free = freePlans[0] ?? null;

  if (families.length === 0 && !free) return null;

  return (
    <div className="space-y-6">
      <div className={`grid gap-5 ${free ? "md:grid-cols-2 xl:grid-cols-4" : "md:grid-cols-3"}`}>
        {free ? <FreeCard plan={free} /> : null}
        {families.map((family, index) => {
          const plan = (family.monthly ?? family.representative) as PublicPlan;
          const featured = index === 1;
          const discounted = plan.effective_price_cents < plan.price_cents;
          return (
            <article
              key={family.key}
              className={`rounded-[28px] border p-6 ring-1 ${
                featured
                  ? "border-emerald-300/30 bg-[linear-gradient(180deg,rgba(16,185,129,0.14),rgba(255,255,255,0.03))] ring-emerald-400/15"
                  : "border-white/10 bg-white/[0.03] ring-white/6"
              }`}
            >
              {featured ? (
                <div className="text-[11px] uppercase tracking-[0.18em] text-emerald-200/80">Most popular</div>
              ) : (
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Plan</div>
              )}
              <h3 className="mt-2 font-display text-2xl font-semibold text-white">{family.label}</h3>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-4xl font-semibold text-white">
                  {formatPlanPrice(plan.effective_price_cents)}
                </span>
                <span className="text-slate-400">/month</span>
              </div>
              {discounted ? (
                <div className="mt-1 text-xs text-fuchsia-200/90">Launch offer active</div>
              ) : null}
              <div className="mt-5 border-b border-white/8 pb-5">
                <div className="text-3xl font-semibold text-emerald-200">
                  {creditHeadlineNumber(plan).toLocaleString()}
                </div>
                {creditCaptionLines(plan).map((line, index) => (
                  <div
                    key={`${line}-${index}`}
                    className={index === 0 ? "text-sm text-slate-400" : "mt-1 text-xs text-slate-500"}
                  >
                    {line}
                  </div>
                ))}
              </div>
              <div className="mt-5">
                <CardBullets plan={plan} />
              </div>
            </article>
          );
        })}
      </div>
      <p className="text-sm leading-6 text-slate-300/70">
        Dual-channel desktop is included on every card, not a separate plan name. Song hint uses
        the Credits-page music cost (one generate returns two songs). Hidden $79 desktop rows stay
        off this page.
      </p>
    </div>
  );
}
