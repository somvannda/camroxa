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
  description: "Choose a CAMXORA plan powered by the same admin-managed pricing used across the platform.",
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
      title="Live pricing pulled from the real CAMXORA catalog."
      description="Plan limits and credit rates come from the same admin-managed system as billing and desktop generation."
      aside={
        <div className="space-y-5">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-slate-400">What this page solves</div>
            <div className="mt-3 font-display text-2xl font-semibold tracking-[-0.05em] text-white">
              One pricing source across website and product.
            </div>
          </div>
          <p className="text-sm leading-6 text-slate-200/72">
            Suno packages, drafts, images, and overage credit rates stay aligned with Admin Plans and
            platform billing — including Primary + Secondary channel as one package.
          </p>
        </div>
      }
    >
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
