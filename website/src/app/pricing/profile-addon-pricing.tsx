import { formatPlanPrice } from "@/lib/plan-pricing";

type AddonQuote = {
  current_channels: number;
  addon_channels: number;
  new_total_channels: number;
  monthly_addon_cents: number;
  max_addon_channels_remaining: number;
};

async function fetchAddonQuote(currentChannels: number): Promise<AddonQuote | null> {
  const platformApiBaseUrl =
    process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL ??
    (process.env.NODE_ENV === "development"
      ? "http://localhost:8000/api/v3"
      : "https://api.camxora.com/api/v3");

  try {
    const response = await fetch(
      `${platformApiBaseUrl}/plans/public/profile-addon-quote?current_channels=${currentChannels}`,
      { next: { revalidate: 60 } },
    );
    if (!response.ok) return null;
    return (await response.json()) as AddonQuote;
  } catch {
    return null;
  }
}

export async function ProfileAddonPricing() {
  const anchorChannels = [2, 4, 6, 8] as const;
  const quotes = await Promise.all(anchorChannels.map((channels) => fetchAddonQuote(channels)));
  const rows = anchorChannels
    .map((channels, index) => ({ channels, quote: quotes[index] }))
    .filter((row) => row.quote && row.quote.max_addon_channels_remaining > 0);

  if (rows.length === 0) return null;

  return (
    <section className="overflow-hidden rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] ring-1 ring-white/6">
      <div className="border-b border-white/8 px-6 py-5">
        <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-emerald-300/80">
          Channel add-ons
        </div>
        <h2 className="mt-2 font-display text-2xl font-semibold tracking-[-0.04em] text-white">
          Add +2 channels without changing your plan
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300/72">
          Each add-on bundle includes 2 channel profiles (up to 10 channels per account). The monthly
          add-on price is fixed — the same whether you have 2, 4, 6, or 8 channels today. Monthly quotas
          scale only after you complete onboarding for the new profiles.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[640px] w-full border-collapse text-left text-sm">
          <thead className="bg-white/[0.03] text-[11px] uppercase tracking-[0.16em] text-slate-400/80">
            <tr>
              <th className="px-6 py-4">Current channels</th>
              <th className="px-6 py-4">Add-on bundle</th>
              <th className="px-6 py-4">New total</th>
              <th className="px-6 py-4">Monthly add-on price</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ channels, quote }) => (
              <tr key={channels} className="border-t border-white/8">
                <td className="px-6 py-4 text-slate-200">{channels} channels</td>
                <td className="px-6 py-4 text-slate-300">+2 channels</td>
                <td className="px-6 py-4 text-white">{quote!.new_total_channels} channels</td>
                <td className="px-6 py-4 font-medium text-emerald-100">
                  {formatPlanPrice(quote!.monthly_addon_cents)}/mo
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
