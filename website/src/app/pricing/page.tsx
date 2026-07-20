import type { Metadata } from "next";

import { ContentPageShell } from "@/components/marketing/content-page-shell";
import { UsageRatesSection } from "@/app/pricing/usage-rates-section";
import {
  PricingComparisonTable,
  type PublicPlan,
} from "@/app/pricing/pricing-comparison-table";
import { ProfileAddonPricing } from "@/app/pricing/profile-addon-pricing";
import { DEFAULT_TERM_DISCOUNTS, type PlanTermDiscounts } from "@/lib/plan-pricing";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Choose a Camxora plan for faceless YouTube music channels — desktop studio, credits, and channel capacity.",
};

async function getPlatformApiBaseUrl(): Promise<string> {
  return (
    process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL ??
    (process.env.NODE_ENV === "development"
      ? "http://localhost:8000/api/v1"
      : "https://api.camxora.com/api/v1")
  );
}

async function getPublicPlans(): Promise<PublicPlan[]> {
  const platformApiBaseUrl = await getPlatformApiBaseUrl();

  try {
    const response = await fetch(`${platformApiBaseUrl}/plans/public`, {
      next: { revalidate: 60 },
    });
    if (!response.ok) return [];
    return (await response.json()) as PublicPlan[];
  } catch {
    return [];
  }
}

async function getTermDiscounts(): Promise<PlanTermDiscounts> {
  const platformApiBaseUrl = await getPlatformApiBaseUrl();

  try {
    const response = await fetch(`${platformApiBaseUrl}/plans/public/term-discounts`, {
      next: { revalidate: 60 },
    });
    if (!response.ok) return DEFAULT_TERM_DISCOUNTS;
    return (await response.json()) as PlanTermDiscounts;
  } catch {
    return DEFAULT_TERM_DISCOUNTS;
  }
}

export default async function PricingPage() {
  const [plans, termDiscounts] = await Promise.all([getPublicPlans(), getTermDiscounts()]);

  return (
    <ContentPageShell
      eyebrow="Pricing"
      title="Plans for faceless music channels."
      description={
        <>
          <p>
            Pick the channel capacity you need. Sandbox pricing may use low test fees while we
            validate the product.
          </p>
          <p>
            Manual faceless production can take{" "}
            <strong className="text-white">2+ hours per channel every day</strong> — and scale into{" "}
            <strong className="text-white">10 hours a day</strong> across multiple channels. With
            Camxora, collapse that grind to about{" "}
            <strong className="text-white">one hour</strong>: one click, then sit back and watch the
            pipeline run.
          </p>
          <p>
            <strong className="text-white">Get monetized — or we refund 100%</strong> of your plan
            payment. We stand behind the result.
          </p>
        </>
      }
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Included today</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              Faceless desktop studio + generation credits.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Drafts, music packages, images, video export, merge allowances, and marketplace template
            access (free + premium packs). Auto YouTube upload is coming soon.
          </p>
          <div className="border-t border-white/8 pt-4 space-y-3 text-sm leading-6 text-slate-200/72">
            <p>
              <span className="font-medium text-white">Time back:</span> from ~10 hours a day of
              manual channel work to ~1 hour with the Camxora pipeline.
            </p>
            <p>
              <span className="font-medium text-white">Monetization guarantee:</span> reach YouTube
              monetization, or get a full plan refund.
            </p>
          </div>
        </div>
      }
    >
      <div className="mb-10 rounded-[28px] border border-emerald-400/20 bg-[linear-gradient(180deg,rgba(16,185,129,0.12),rgba(255,255,255,0.03))] p-6 ring-1 ring-emerald-400/15 md:p-7">
        <div className="text-[11px] uppercase tracking-[0.22em] text-emerald-100/70">
          Monetization guarantee
        </div>
        <h2 className="mt-3 font-display text-2xl font-semibold tracking-[-0.04em] text-white md:text-3xl">
          Get monetized — or we refund 100%.
        </h2>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-200/78 md:text-base md:leading-8">
          We stand behind Camxora with a simple promise: if you use the studio to build and publish
          your faceless music channel and you{" "}
          <strong className="text-white">don&apos;t reach YouTube monetization</strong>, we&apos;ll{" "}
          <strong className="text-white">refund your plan payment in full</strong>. Contact{" "}
          <a className="text-emerald-100 underline-offset-2 hover:underline" href="mailto:support@camxora.com">
            support@camxora.com
          </a>{" "}
          with your account, invoice, and channel details. You must follow Camxora&apos;s workflow
          and YouTube policies — we refund the plan fee, not lost AdSense earnings.
        </p>
      </div>

      {plans.length === 0 ? (
        <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6 text-sm text-slate-200/72">
          No public plans are active yet. Enable at least one paid plan in the Admin Portal to publish pricing here.
        </div>
      ) : (
        <div className="space-y-10">
          <PricingComparisonTable plans={plans} termDiscounts={termDiscounts} />
          <ProfileAddonPricing />
          <UsageRatesSection />
        </div>
      )}
    </ContentPageShell>
  );
}
