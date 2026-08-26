import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { V3_PLAN_OPS, type V3PlanOp } from '@/types/v3-billing';

export type CreditsOnlyFormValues = {
  monthly_credits: string;
  daily_credits: string;
  is_public: boolean;
  is_active: boolean;
  pricing_features: string;
  pricing_credit_lines: string;
  ops: Record<V3PlanOp, string>;
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

const OP_LABELS: Record<V3PlanOp, string> = {
  lyric: 'Lyric',
  title: 'Title',
  album: 'Album',
  music: 'Music (1 generate = 2 versions)',
  style: 'Style',
  image: 'Image',
  video: 'Video',
  merge: 'Merge',
};

export function emptyCreditsOnlyForm(): CreditsOnlyFormValues {
  return {
    monthly_credits: '0',
    daily_credits: '0',
    is_public: false,
    is_active: true,
    pricing_features: '',
    pricing_credit_lines: '',
    ops: {
      lyric: '',
      title: '',
      album: '',
      music: '',
      style: '',
      image: '',
      video: '',
      merge: '',
    },
  };
}

export function formFromCredits(plan: {
  monthly_credits?: number | null;
  daily_credits?: number | null;
  is_public?: boolean;
  is_active?: boolean;
  pricing_features?: string[] | null;
  pricing_credit_lines?: string[] | null;
  lyric_credits?: number | null;
  title_credits?: number | null;
  album_credits?: number | null;
  music_credits?: number | null;
  style_credits?: number | null;
  image_credits?: number | null;
  video_credits?: number | null;
  merge_credits?: number | null;
}): CreditsOnlyFormValues {
  const opValue = (value: number | null | undefined) =>
    value == null ? '' : String(value);
  return {
    monthly_credits: String(plan.monthly_credits ?? 0),
    daily_credits: String(plan.daily_credits ?? 0),
    is_public: Boolean(plan.is_public),
    is_active: plan.is_active !== false,
    pricing_features: pricingFeaturesToText(plan.pricing_features),
    pricing_credit_lines: pricingFeaturesToText(plan.pricing_credit_lines),
    ops: {
      lyric: opValue(plan.lyric_credits),
      title: opValue(plan.title_credits),
      album: opValue(plan.album_credits),
      music: opValue(plan.music_credits),
      style: opValue(plan.style_credits),
      image: opValue(plan.image_credits),
      video: opValue(plan.video_credits),
      merge: opValue(plan.merge_credits),
    },
  };
}

export function parseOptionalCredits(value: string): number | null | typeof Number.NaN {
  const text = value.trim();
  if (text === '') return null;
  const parsed = Number(text);
  if (!Number.isInteger(parsed) || parsed < 0) return Number.NaN;
  return parsed;
}

export function CreditsOnlyPlanFields({
  values,
  onChange,
}: {
  values: CreditsOnlyFormValues;
  onChange: (next: CreditsOnlyFormValues) => void;
}) {
  const monthly = Number.parseInt(values.monthly_credits, 10);
  const daily = Number.parseInt(values.daily_credits, 10);
  const songPreview =
    Number.isInteger(monthly) && monthly >= 0
      ? `≈ ${Math.floor(monthly / 10) * 2} songs (10 credits = 1 generate = 2 songs)`
      : 'Enter a whole number of monthly credits.';
  const dailySongPreview =
    Number.isInteger(daily) && daily > 0
      ? `≈ ${Math.floor(daily / 10) * 2} songs/day`
      : null;

  return (
    <div className="space-y-4 rounded-lg border border-violet-500/20 bg-violet-500/5 p-4">
      <div>
        <h4 className="text-sm font-semibold text-slate-100">Credits-only (v3)</h4>
        <p className="mt-1 text-xs text-slate-500">
          Grants and per-op amounts live on this plan row. Empty per-op fields fall back to the
          Credits page. 0 means included. Add-on profile slots do not multiply these amounts.
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
              ? ['daily credits', `≈ ${Math.floor(daily / 10) * 2} songs/day`, 'Resets at midnight'].join('\n')
              : Number.isInteger(monthly) && monthly > 0
                ? ['credits per month', `≈ ${Math.floor(monthly / 10) * 2} songs/mo`].join('\n')
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
        Keep hidden legacy plans active but not public. Public = website / music-web cards.
      </p>

      <div className="grid gap-3 md:grid-cols-2">
        {V3_PLAN_OPS.map((op) => (
          <div key={op} className="space-y-1.5">
            <Label htmlFor={`v3-op-${op}`}>{OP_LABELS[op]}</Label>
            <Input
              id={`v3-op-${op}`}
              type="number"
              min={0}
              placeholder="Credits page"
              value={values.ops[op]}
              onChange={(e) =>
                onChange({
                  ...values,
                  ops: { ...values.ops, [op]: e.target.value },
                })
              }
            />
          </div>
        ))}
      </div>
    </div>
  );
}
