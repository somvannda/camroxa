import type { Metadata } from "next";

import { MarketingFooter, MarketingHeader } from "@/components/marketing/site-chrome";
import { PricingCards, type CreditPack } from "@/app/pricing/pricing-cards";
import { getMusicWebBaseUrl, getUserPortalBaseUrl } from "@/lib/site-urls";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Buy credit packs for AI music generation — one-time purchase, no subscription, credits valid for 30 days.",
};

async function getPlatformApiBaseUrl(): Promise<string> {
  const base =
    process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL ??
    (process.env.NODE_ENV === "development"
      ? "http://localhost:8000/api/v3"
      : "https://api.camxora.com/api/v3");
  // The deployed env still carries an older ".../api/v1" value (fine for the v1
  // aliases like /plans/public, but /topups/packs is v3-only). Pin the version so
  // a stale base cannot silently 404 the catalog and leave the page empty.
  return base.replace(/\/api\/v\d+\/?$/, "/api/v3");
}

/**
 * Credit packs are the only product now that subscriptions are retired.
 * `GET /api/v3/topups/packs` is a public catalog endpoint, so the marketing page
 * reads the same pack rows the in-app store sells — no hardcoded prices here.
 */
async function getCreditPacks(): Promise<CreditPack[]> {
  const platformApiBaseUrl = await getPlatformApiBaseUrl();

  try {
    const response = await fetch(`${platformApiBaseUrl}/topups/packs`, {
      next: { revalidate: 60 },
    });
    if (!response.ok) return [];
    const payload = (await response.json()) as { packs?: CreditPack[] };
    return Array.isArray(payload.packs) ? payload.packs : [];
  } catch {
    return [];
  }
}

export default async function PricingPage() {
  const packs = await getCreditPacks();
  const userPortalBaseUrl = getUserPortalBaseUrl();
  const musicWebBaseUrl = getMusicWebBaseUrl();

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-gradient-to-b from-[#0a0e27] to-[#1a1f3a]">
      <MarketingHeader userPortalBaseUrl={userPortalBaseUrl} />
      <main className="relative mx-auto w-full max-w-7xl flex-1 px-4 py-16 md:px-10 md:py-20">
        {packs.length === 0 ? (
          <div className="rounded-2xl border border-purple-500/20 bg-[#0c1230] p-6 text-sm text-gray-300">
            Credit packs are temporarily unavailable. Please check back shortly, or buy credits
            directly in the Camxora Music app.
          </div>
        ) : (
          <PricingCards packs={packs} musicWebBaseUrl={musicWebBaseUrl} />
        )}
      </main>
      <MarketingFooter userPortalBaseUrl={userPortalBaseUrl} />
    </div>
  );
}
