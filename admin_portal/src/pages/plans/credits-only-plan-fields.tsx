import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

export type CreditsOnlyFormValues = {
  monthly_credits: string;
  daily_credits: string;
  is_public: boolean;
  is_active: boolean;
  pricing_features: string;
  pricing_credit_lines: string;
};

export function pricingFeaturesToText(lines?: string[] | null): string {
  return (lines ?? []).map((line) => line.trim()).filter(Boolean).join('\n');
}

export function pricingFeaturesFromText(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

export function emptyCreditsOnlyForm(): CreditsOnlyFormValues {
  return {
    monthly_credits: '0',
    daily_credits: '0',
    is_public: false,
    is_active: true,
    pricing_features: '',
    pricing_credit_lines: '',
  };
}

export function formFromCredits(plan: {
  monthly_credits?: number | null;
  daily_credits?: number | null;
  is_public?: boolean;
  is_active?: boolean;
  pricing_features?: string[] | null;
  pricing_credit_lines?: string[] | null;
}): CreditsOnlyFormValues {
  return {
    monthly_credits: String(plan.monthly_credits ?? 0),
    daily_credits: String(plan.daily_credits ?? 0),
    is_public: Boolean(plan.is_public),
    is_active: plan.is_active !== false,
    pricing_features: pricingFeaturesToText(plan.pricing_features),
    pricing_credit_lines: pricingFeaturesToText(plan.pricing_credit_lines),
  };
}

function songHint(credits: number, perGenerate: number): number {
  if (!Number.isFinite(credits) || credits < 0 || perGenerate <= 0) return 0;
  return Math.floor(credits / perGenerate) * 2;
}

export function CreditsOnlyPlanFields({
  values,
  onChange,
  creditsPerGenerate = 10,
}: {
  values: CreditsOnlyFormValues;
  onChange: (next: CreditsOnlyFormValues) => void;
  creditsPerGenerate?: number;
}) {
  const monthly = Number.parseInt(values.monthly_credits, 10);
  const daily = Number.parseInt(values.daily_credits, 10);
  const per = creditsPerGenerate > 0 ? creditsPerGenerate : 10;
  const songPreview =
    Number.isInteger(monthly) && monthly >= 0
      ? `≈ ${songHint(monthly, per)} songs (${per} credits = 1 generate = 2 songs)`
      : 'Enter a whole number of monthly credits.';
  const dailySongPreview =
    Number.isInteger(daily) && daily > 0 ? `≈ ${songHint(daily, per)} songs/day` : null;

  return (
    <div className="space-y-4 rounded-lg border border-violet-500/20 bg-violet-500/5 p-4">
      <div>
        <h4 className="text-sm font-semibold text-slate-100">Credits-only (v3)</h4>
        <p className="mt-1 text-xs text-slate-500">
          This plan only grants monthly or daily credits. Generate charges the Credits page list
          price. Add-on profile slots do not multiply these amounts.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="v3-monthly-credits">Monthly credits (period grant)</Label>
          <Input
            id="v3-monthly-credits"
            type="number"
            min={0}
            value={values.monthly_credits}
            onChange={(e) => onChange({ ...values, monthly_credits: e.target.value })}
          />
          <p className="text-xs text-slate-500">{songPreview}</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="v3-daily-credits">Daily credits (optional cap / free grant)</Label>
          <Input
            id="v3-daily-credits"
            type="number"
            min={0}
            value={values.daily_credits}
            onChange={(e) => onChange({ ...values, daily_credits: e.target.value })}
          />
          {dailySongPreview ? <p className="text-xs text-slate-500">{dailySongPreview}</p> : null}
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="v3-pricing-features">Pricing page features</Label>
        <Textarea
          id="v3-pricing-features"
          rows={5}
          value={values.pricing_features}
          onChange={(e) => onChange({ ...values, pricing_features: e.target.value })}
          placeholder={'Web Create\nDesktop studio\nDual channels\nTop-up packs'}
        />
        <p className="text-xs text-slate-500">
          One line per bullet on /pricing. Empty lines are ignored. Leave blank to use the default
          Free or paid list.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="v3-pricing-credit-lines">Pricing credit captions</Label>
        <Textarea
          id="v3-pricing-credit-lines"
          rows={4}
          value={values.pricing_credit_lines}
          onChange={(e) => onChange({ ...values, pricing_credit_lines: e.target.value })}
          placeholder={
            Number.isInteger(daily) && daily > 0
              ? ['daily credits', `≈ ${songHint(daily, per)} songs/day`, 'Resets at midnight'].join('\n')
              : Number.isInteger(monthly) && monthly > 0
                ? ['credits per month', `≈ ${songHint(monthly, per)} songs/mo`].join('\n')
                : 'credits'
          }
        />
        <p className="text-xs text-slate-500">
          Lines under the big credit number. First line is the unit label; extra lines are the
          gray hints. Leave blank to follow daily/monthly credits (no midnight text when daily is
          0).
        </p>
      </div>

      <div className="flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={values.is_active}
            onChange={(e) => onChange({ ...values, is_active: e.target.checked })}
            className="h-4 w-4 rounded border-slate-600"
          />
          Active
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={values.is_public}
            onChange={(e) => onChange({ ...values, is_public: e.target.checked })}
            className="h-4 w-4 rounded border-slate-600"
          />
          Public catalog
        </label>
      </div>
      <p className="text-xs text-slate-500">
        Keep hidden legacy plans active but not public. Public = website / music-web cards. Change
        music / lyric / style costs on Credits.
      </p>
    </div>
  );
}
