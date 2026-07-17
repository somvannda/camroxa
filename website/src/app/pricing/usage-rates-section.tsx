type PublicUsageRateItem = {
  operation_type: string;
  label: string;
  credits_per_operation: number | null;
  available: boolean;
  message: string | null;
};

type PublicUsageRates = {
  updated_at: string;
  items: PublicUsageRateItem[];
  estimated_full_song_credits: number | null;
  disclaimer: string;
};

function formatCredits(value: number): string {
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 4 });
}

function platformApiBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL ??
    (process.env.NODE_ENV === "development"
      ? "http://localhost:8000/api/v1"
      : "https://api.camxora.com/api/v1")
  );
}

async function getPublicUsageRates(): Promise<PublicUsageRates | null> {
  try {
    const response = await fetch(`${platformApiBaseUrl()}/plans/public/usage-rates`, {
      next: { revalidate: 300 },
    });
    if (!response.ok) return null;
    return (await response.json()) as PublicUsageRates;
  } catch {
    return null;
  }
}

export async function UsageRatesSection() {
  const rates = await getPublicUsageRates();
  if (!rates || rates.items.length === 0) return null;

  const availableItems = rates.items.filter((item) => item.available && item.credits_per_operation != null);

  return (
    <section className="rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-6 ring-1 ring-white/6">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Credit usage rates</div>
          <h2 className="mt-2 font-display text-2xl font-semibold tracking-[-0.04em] text-white">
            Live per-operation costs
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-200/72">
            Plans include draft, Suno package, and image allowances. Overage and lifetime wallet
            use the same rates — music is one charge per Suno package (Primary + Secondary channel), not per track.
          </p>
        </div>
        {rates.estimated_full_song_credits != null ? (
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-slate-100/85">
            <div className="text-xs uppercase tracking-[0.16em] text-slate-300/55">
              Estimated song package (overage)
            </div>
            <div className="mt-1 font-display text-2xl font-semibold text-white">
              {formatCredits(rates.estimated_full_song_credits)} credits
            </div>
            <div className="mt-1 text-xs text-slate-300/60">Lyric + title + album + 1 Suno package</div>
          </div>
        ) : null}
      </div>

      <div className="mt-6 overflow-hidden rounded-2xl border border-white/8">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/[0.03] text-xs uppercase tracking-[0.16em] text-slate-300/60">
            <tr>
              <th className="px-4 py-3 font-medium">Operation</th>
              <th className="px-4 py-3 font-medium">Credits</th>
            </tr>
          </thead>
          <tbody>
            {rates.items.map((item) => (
              <tr key={item.operation_type} className="border-t border-white/6 text-slate-200/80">
                <td className="px-4 py-3">{item.label}</td>
                <td className="px-4 py-3">
                  {item.available && item.credits_per_operation != null ? (
                    <span className="font-medium text-white">
                      {formatCredits(item.credits_per_operation)}
                    </span>
                  ) : (
                    <span className="text-slate-400">Unavailable</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {availableItems.length > 0 ? (
        <p className="mt-4 text-xs leading-5 text-slate-300/55">{rates.disclaimer}</p>
      ) : (
        <p className="mt-4 text-xs leading-5 text-slate-300/55">
          Usage rates are not published yet. Configure AI routing and credit pricing in the Admin Portal.
        </p>
      )}
    </section>
  );
}
