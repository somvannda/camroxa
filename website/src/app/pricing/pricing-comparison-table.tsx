import { Check } from "lucide-react";

import {
  channelFamilyLabel,
  formatPlanPrice,
  groupPlansIntoChannelFamilies,
  termPriceCents,
  type ChannelPlanFamily,
} from "@/app/pricing/plan-channel-families";
import {
  billingTermQuotes,
  DEFAULT_TERM_DISCOUNTS,
  type PlanTermDiscounts,
} from "@/lib/plan-pricing";

type PublicPlanOffer = {
  id: string;
  promo_price_cents: number;
  max_redemptions: number;
  current_redemptions: number;
  remaining_redemptions: number;
  is_active: boolean;
};

export type PublicPlan = {
  id: string;
  name: string;
  price_cents: number;
  effective_price_cents: number;
  billing_cycle_days: number | null;
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

type CellValue =
  | { kind: "text"; value: string }
  | { kind: "check" };

type ComparisonRow = {
  label: string;
  values: CellValue[];
  emphasized?: boolean;
};

type ComparisonSection = {
  title: string;
  rows: ComparisonRow[];
};

function perChannelMonthlyTotal(total: number | null, channels: number): string {
  if (total === null) return "Unlimited";
  if (channels <= 0) return "—";
  return Math.round(total / channels).toLocaleString();
}

function formatLimit(value: number | null): string {
  if (value === null) return "Unlimited";
  return value.toLocaleString();
}

function planBadge(index: number, total: number): string {
  if (total >= 3 && index === total - 1) return " 👑";
  if (total >= 2 && index === Math.floor((total - 1) / 2)) return " ⭐";
  return "";
}

function isFeaturedColumn(index: number, total: number): boolean {
  return total >= 2 && index === Math.floor((total - 1) / 2);
}

function cellForAllFamilies(families: ChannelPlanFamily[], value: CellValue): CellValue[] {
  return families.map(() => value);
}

function dailyAccountImages(plan: PublicPlan): number {
  return plan.profile_allowance * plan.daily_image_limit_per_channel;
}

function billingCell(
  family: ChannelPlanFamily,
  term: "monthly" | "semiAnnual" | "annual",
  termDiscounts: PlanTermDiscounts,
): CellValue {
  const monthly = termPriceCents(family, "monthly");
  if (monthly == null) {
    return { kind: "text", value: "—" };
  }

  if (term === "monthly") {
    return { kind: "text", value: formatPlanPrice(monthly) };
  }

  const quotes = billingTermQuotes(monthly, termDiscounts);
  const total = term === "semiAnnual" ? quotes.semiAnnual : quotes.annual;

  return {
    kind: "text",
    value: formatPlanPrice(total),
  };
}

function buildComparisonSections(
  families: ChannelPlanFamily[],
  termDiscounts: PlanTermDiscounts,
): ComparisonSection[] {
  const plans = families.map((family) => family.representative);
  const check: CellValue = { kind: "check" };

  const summaryRows: ComparisonRow[] = [
    {
      label: "Price",
      emphasized: true,
      values: families.map((family) => {
        const monthly = termPriceCents(family, "monthly");
        if (monthly == null) {
          return { kind: "text", value: "—" };
        }
        return { kind: "text", value: `${formatPlanPrice(monthly)}/month` };
      }),
    },
    {
      label: "Channels",
      values: families.map((family) => ({
        kind: "text",
        value: family.channels.toLocaleString(),
      })),
    },
  ];

  const accessRows: ComparisonRow[] = [
    {
      label: "Desktop Studio",
      values: cellForAllFamilies(families, check),
    },
    {
      label: "Dashboard & Billing",
      values: cellForAllFamilies(families, check),
    },
    {
      label: "Channel Profiles",
      values: families.map((family) => ({
        kind: "text",
        value: family.channels.toLocaleString(),
      })),
    },
  ];

  const generationRows: ComparisonRow[] = [
    {
      label: "Suno packages per Channel / Day",
      values: plans.map((plan) => ({
        kind: "text",
        value: plan.daily_song_limit_per_channel.toLocaleString(),
      })),
    },
    {
      label: "Images per Channel / Day (BG + TH)",
      values: plans.map((plan) => ({
        kind: "text",
        value: plan.daily_image_limit_per_channel.toLocaleString(),
      })),
    },
    {
      label: "Total Images / Day (BG + TH)",
      values: plans.map((plan) => ({
        kind: "text",
        value: dailyAccountImages(plan).toLocaleString(),
      })),
    },
    {
      label: "Suno packages per Channel / Month",
      values: plans.map((plan) => ({
        kind: "text",
        value: perChannelMonthlyTotal(plan.monthly_song_limit, plan.profile_allowance),
      })),
    },
    {
      label: "Images per Channel / Month",
      values: plans.map((plan) => ({
        kind: "text",
        value: perChannelMonthlyTotal(plan.monthly_image_limit, plan.profile_allowance),
      })),
    },
    {
      label: "Total Suno packages / Month",
      values: plans.map((plan) => ({
        kind: "text",
        value: formatLimit(plan.monthly_song_limit),
      })),
    },
    {
      label: "Total Images / Month",
      values: plans.map((plan) => ({
        kind: "text",
        value: formatLimit(plan.monthly_image_limit),
      })),
    },
    {
      label: "Primary + Secondary channel tracks",
      values: cellForAllFamilies(families, check),
    },
    {
      label: "Album / Lyrics Generation",
      values: plans.map((plan) =>
        plan.monthly_draft_limit === 0
          ? { kind: "text", value: "—" }
          : check,
      ),
    },
  ];

  const videoRows: ComparisonRow[] = [
    {
      label: "Video Maker",
      values: plans.map((plan) =>
        plan.monthly_video_limit === null
          ? check
          : { kind: "text", value: formatLimit(plan.monthly_video_limit) },
      ),
    },
    {
      label: "Video Merger",
      values: plans.map((plan) =>
        plan.monthly_merge_limit === null
          ? check
          : { kind: "text", value: formatLimit(plan.monthly_merge_limit) },
      ),
    },
    {
      label: "Ready Templates",
      values: plans.map((plan) => ({
        kind: "text",
        value: plan.profile_allowance.toLocaleString(),
      })),
    },
    {
      label: "Custom Templates",
      values: families.map(() => ({ kind: "text", value: "Unlimited" })),
    },
    {
      label: "Auto YouTube Upload",
      values: cellForAllFamilies(families, check),
    },
  ];

  const billingRows: ComparisonRow[] = [
    {
      label: "Monthly",
      values: families.map((family) => billingCell(family, "monthly", termDiscounts)),
    },
    {
      label: `6 Months (${termDiscounts.semi_annual_discount_percent}% OFF)`,
      values: families.map((family) => billingCell(family, "semiAnnual", termDiscounts)),
    },
    {
      label: `Annual (${termDiscounts.annual_discount_percent}% OFF)`,
      values: families.map((family) => billingCell(family, "annual", termDiscounts)),
    },
  ];

  return [
    { title: "Summary", rows: summaryRows },
    { title: "Access", rows: accessRows },
    { title: "AI Generation", rows: generationRows },
    { title: "Video", rows: videoRows },
    { title: "Billing", rows: billingRows },
  ];
}

function ComparisonCell({ cell }: { cell: CellValue }) {
  if (cell.kind === "check") {
    return (
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-emerald-300/20 bg-emerald-400/10 text-emerald-100">
        <Check className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="sr-only">Included</span>
      </span>
    );
  }

  return <span>{cell.value}</span>;
}

function PlanHeaderCell({
  family,
  index,
  total,
}: {
  family: ChannelPlanFamily;
  index: number;
  total: number;
}) {
  const featured = isFeaturedColumn(index, total);
  const plan = family.representative;
  const discounted = plan.effective_price_cents < plan.price_cents;

  return (
    <th
      scope="col"
      className={`min-w-[140px] px-4 py-4 text-left align-bottom ${
        featured ? "bg-white/[0.04]" : ""
      }`}
    >
      <div className={`text-sm font-semibold ${featured ? "text-white" : "text-slate-100"}`}>
        {channelFamilyLabel(family.channels)}
        {planBadge(index, total)}
      </div>
      {discounted ? (
        <div className="mt-1 text-xs text-fuchsia-200/90">Launch offer active</div>
      ) : null}
    </th>
  );
}

function SectionHeaderRow({
  title,
  families,
}: {
  title: string;
  families: ChannelPlanFamily[];
}) {
  if (title === "Summary") return null;

  return (
    <tr className="border-t border-white/10 bg-white/[0.02]">
      <th
        scope="row"
        className="sticky left-0 z-10 bg-[#0b1020]/95 px-4 py-3 text-left text-[11px] font-medium uppercase tracking-[0.18em] text-slate-300/70 backdrop-blur"
      >
        {title}
      </th>
      {families.map((family, index) => (
        <th
          key={`${title}-${family.channels}`}
          scope="col"
          className={`px-4 py-3 text-left text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400/75 ${
            isFeaturedColumn(index, families.length) ? "bg-white/[0.03]" : ""
          }`}
        >
          {channelFamilyLabel(family.channels)}
          {planBadge(index, families.length)}
        </th>
      ))}
    </tr>
  );
}

function ComparisonDataRow({
  row,
  planCount,
  featuredIndex,
}: {
  row: ComparisonRow;
  planCount: number;
  featuredIndex: number;
}) {
  return (
    <tr className="border-t border-white/6 text-sm text-slate-200/82">
      <th
        scope="row"
        className={`px-4 py-3 text-left font-normal text-slate-300/88 ${
          row.emphasized ? "font-medium text-white" : ""
        }`}
      >
        {row.label}
      </th>
      {row.values.slice(0, planCount).map((cell, index) => (
        <td
          key={`${row.label}-${index}`}
          className={`px-4 py-3 ${index === featuredIndex ? "bg-white/[0.03] font-medium text-white" : ""}`}
        >
          <ComparisonCell cell={cell} />
        </td>
      ))}
    </tr>
  );
}

function PricingNotes({ plans }: { plans: PublicPlan[] }) {
  const notes = [
    "Each channel profile connects to your YouTube channel and is managed through the same account controls as billing.",
    "Need more channels without changing plans? Add +2 channel profiles at a time (up to 10 channels per account). Monthly quotas increase only after you finish onboarding for the new profiles.",
    "Draft, Suno package, and image allowances reset at the start of each billing cycle.",
    "Wallet credits can be purchased separately for overage without upgrading your plan.",
    "6-month and annual checkout totals use the live monthly plan price plus the billing term discounts saved in Admin → Plans (same math as Sync 6-month & annual prices).",
  ];

  const offers = plans.filter((plan) => plan.offer);

  return (
    <div className="border-t border-white/8 px-4 py-5 md:px-6">
      <ul className="space-y-2 text-sm leading-6 text-slate-300/72">
        {notes.map((note) => (
          <li key={note} className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-emerald-300/20 bg-emerald-400/10 text-emerald-100">
              <Check className="h-3 w-3" aria-hidden="true" />
            </span>
            <span>{note}</span>
          </li>
        ))}
      </ul>

      {offers.length > 0 ? (
        <div className="mt-4 rounded-2xl border border-fuchsia-300/18 bg-fuchsia-400/8 p-4 text-sm text-fuchsia-50/90">
          {offers.map((plan) => (
            <div key={plan.id}>
              {plan.name}: promotional pricing active —{" "}
              {plan.offer?.remaining_redemptions.toLocaleString()} redemption
              {plan.offer?.remaining_redemptions === 1 ? "" : "s"} remaining.
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function PricingComparisonTable({
  plans,
  termDiscounts = DEFAULT_TERM_DISCOUNTS,
}: {
  plans: PublicPlan[];
  termDiscounts?: PlanTermDiscounts;
}) {
  const families = groupPlansIntoChannelFamilies(plans);
  if (families.length === 0) return null;

  const sections = buildComparisonSections(families, termDiscounts);
  const featuredIndex = Math.floor((families.length - 1) / 2);

  return (
    <div className="overflow-hidden rounded-[32px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] ring-1 ring-white/6">
      <div className="overflow-x-auto">
        <table className="min-w-[720px] w-full border-collapse text-left">
          <thead className="bg-white/[0.03]">
            <tr>
              <th
                scope="col"
                className="sticky left-0 z-10 min-w-[220px] bg-[#0b1020]/95 px-4 py-4 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-400/80 backdrop-blur"
              >
                Feature
              </th>
              {families.map((family, index) => (
                <PlanHeaderCell
                  key={family.channels}
                  family={family}
                  index={index}
                  total={families.length}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {sections.flatMap((section) => [
              <SectionHeaderRow
                key={`${section.title}-header`}
                title={section.title}
                families={families}
              />,
              ...section.rows.map((row) => (
                <ComparisonDataRow
                  key={`${section.title}-${row.label}`}
                  row={row}
                  planCount={families.length}
                  featuredIndex={featuredIndex}
                />
              )),
            ])}
          </tbody>
        </table>
      </div>

      <PricingNotes plans={plans} />
    </div>
  );
}
