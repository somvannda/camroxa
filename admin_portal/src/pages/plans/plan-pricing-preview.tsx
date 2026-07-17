import {
  billingTermQuotes,
  formatChannelPlanName,
  formatUsd,
  linearPlanMonthlyCents,
  roundWholeDollars,
} from '@/lib/plan-tier-pricing';

type PlanPricingPreviewProps = {
  priceCents: number;
  profileAllowance: number;
  billingCycleDays: number;
  blockPriceCents?: number;
  semiAnnualDiscountPercent?: number;
  annualDiscountPercent?: number;
  addonMonthlyCents?: number;
};

export function PlanPricingPreview({
  priceCents: _priceCents,
  profileAllowance,
  billingCycleDays,
  blockPriceCents = 7900,
  semiAnnualDiscountPercent = 15,
  annualDiscountPercent = 25,
  addonMonthlyCents = 0,
}: PlanPricingPreviewProps) {
  const linearMonthly = linearPlanMonthlyCents(blockPriceCents, profileAllowance);
  const combinedMonthly = roundWholeDollars(linearMonthly + addonMonthlyCents);
  const terms = billingTermQuotes(combinedMonthly, {
    semiAnnualDiscountPercent,
    annualDiscountPercent,
  });
  const suggestedName = formatChannelPlanName(profileAllowance, billingCycleDays);
  const selectedTerm = terms.find((term) => term.billingCycleDays === billingCycleDays);

  return (
    <div className="rounded-xl border border-cyan-400/15 bg-cyan-400/5 p-4 text-sm text-slate-200">
      <div className="text-xs uppercase tracking-[0.16em] text-cyan-200/80">Channel plan preview</div>
      <p className="mt-2 text-sm text-slate-300">
        <span className="font-medium text-white">{profileAllowance} channels</span> ×{' '}
        {formatUsd(blockPriceCents)} per 2-channel block ={' '}
        <span className="font-medium text-white">{formatUsd(linearMonthly)}/mo</span>
        {addonMonthlyCents > 0 ? (
          <>
            {' '}
            + add-ons {formatUsd(addonMonthlyCents)}/mo ={' '}
            <span className="font-medium text-white">{formatUsd(combinedMonthly)}/mo combined</span>
          </>
        ) : null}
      </p>
      <div className="mt-3 text-xs text-slate-400">Suggested plan name</div>
      <div className="mt-1 font-medium text-white">{suggestedName}</div>
      <div className="mt-3">
        <div className="text-xs text-slate-400">
          Billing terms ({semiAnnualDiscountPercent}% / {annualDiscountPercent}% discounts on combined monthly)
        </div>
        <ul className="mt-1 space-y-1">
          {terms.map((term) => (
            <li key={term.label} className={term.billingCycleDays === billingCycleDays ? 'text-cyan-100' : ''}>
              {term.label}: {formatUsd(term.totalCents)} ({term.billingCycleDays} days)
            </li>
          ))}
        </ul>
      </div>
      {selectedTerm ? (
        <p className="mt-3 text-xs text-slate-400">
          Selected checkout row should use {formatUsd(selectedTerm.totalCents)} for this term (whole dollars, no cents).
        </p>
      ) : null}
      <p className="mt-3 text-xs leading-5 text-slate-400">
        Create one plan row per channel count × billing term. Enter the monthly block price and channels — term buttons
        apply discounts to the calculated total.
      </p>
    </div>
  );
}

export function SmartPlanPriceCalculator({
  blockPriceCents,
  profileAllowance,
  billingCycleDays,
  semiAnnualDiscountPercent,
  annualDiscountPercent,
  onApplyPrice,
}: {
  blockPriceCents: number;
  profileAllowance: number;
  billingCycleDays: number;
  semiAnnualDiscountPercent: number;
  annualDiscountPercent: number;
  onApplyPrice: (priceCents: number, billingCycleDays: number) => void;
}) {
  const monthly = linearPlanMonthlyCents(blockPriceCents, profileAllowance);
  const terms = billingTermQuotes(monthly, {
    semiAnnualDiscountPercent,
    annualDiscountPercent,
  });

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-3 text-sm">
      <div className="text-xs uppercase tracking-[0.14em] text-slate-400">Smart price calculator</div>
      <p className="mt-2 text-slate-300">
        Base monthly for {profileAllowance} channels: {formatUsd(monthly)}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {terms.map((term) => (
          <button
            key={term.label}
            type="button"
            className={`rounded-md border px-3 py-1.5 text-xs ${
              term.billingCycleDays === billingCycleDays
                ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-100'
                : 'border-slate-600 text-slate-300 hover:bg-slate-800'
            }`}
            onClick={() => onApplyPrice(term.totalCents, term.billingCycleDays)}
          >
            {term.label}: {formatUsd(term.totalCents)}
          </button>
        ))}
      </div>
    </div>
  );
}
