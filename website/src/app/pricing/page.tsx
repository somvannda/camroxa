import type { Metadata } from "next";

import { MarketingFooter, MarketingHeader } from "@/components/marketing/site-chrome";
import { PricingCards, type PublicPlan } from "@/app/pricing/pricing-cards";
import { getMusicWebBaseUrl, getUserPortalBaseUrl } from "@/lib/site-urls";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Choose Starter, Creator, or Studio credits — same plans on web and desktop.",
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

export default async function PricingPage() {
  const plans = await getPublicPlans();
  const userPortalBaseUrl = getUserPortalBaseUrl();
  const musicWebBaseUrl = getMusicWebBaseUrl();

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-gradient-to-b from-[#0a0e27] to-[#1a1f3a]">
      <MarketingHeader userPortalBaseUrl={userPortalBaseUrl} />
      <main className="relative mx-auto w-full max-w-7xl flex-1 px-4 py-16 md:px-10 md:py-20">
        {plans.length === 0 ? (
          <div className="rounded-2xl border border-purple-500/20 bg-[#0c1230] p-6 text-sm text-gray-300">
            No public plans are active yet. Enable at least one paid plan in the Admin Portal to
            publish pricing here.
          </div>
        ) : (
          <PricingCards plans={plans} musicWebBaseUrl={musicWebBaseUrl} />
        )}
      </main>
      <MarketingFooter userPortalBaseUrl={userPortalBaseUrl} />
    </div>
  );
}
