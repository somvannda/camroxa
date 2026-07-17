import type { PublicPlan } from "@/lib/billing";
import {
  channelFamilyLabel,
  groupPlansIntoChannelFamilies,
  termPriceCents,
  type ChannelPlanFamily,
} from "@/lib/plan-channel-families";
import {
  billingTermQuotes,
  formatPlanPrice,
  type PlanTermDiscounts,
} from "@/lib/plan-pricing";

export type CellValue = { kind: "text"; value: string } | { kind: "check" };

export type ComparisonRow = {
  label: string;
  values: CellValue[];
  emphasized?: boolean;
};

export type ComparisonSection = {
  title: string;
  rows: ComparisonRow[];
};

function perChannelMonthlyTotal(total: number | null, channels: number): string {
  if (total === null) return "Unlimited";
  if (channels <= 0) return "—";
  return Math.round(total / channels).toLocaleString();
}

function formatLimit(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Unlimited";
  return value.toLocaleString();
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

export function buildComparisonSections(
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
    { label: "Desktop Studio", values: cellForAllFamilies(families, check) },
    { label: "Dashboard & Billing", values: cellForAllFamilies(families, check) },
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
        plan.monthly_draft_limit === 0 ? { kind: "text", value: "—" } : check,
      ),
    },
  ];

  const videoRows: ComparisonRow[] = [
    {
      label: "Video Maker",
      values: plans.map((plan) =>
        plan.monthly_video_limit === null || plan.monthly_video_limit === undefined
          ? check
          : { kind: "text", value: formatLimit(plan.monthly_video_limit) },
      ),
    },
    {
      label: "Video Merger",
      values: plans.map((plan) =>
        plan.monthly_merge_limit === null || plan.monthly_merge_limit === undefined
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

export function planBadge(index: number, total: number): string {
  if (total >= 3 && index === total - 1) return " 👑";
  if (total >= 2 && index === Math.floor((total - 1) / 2)) return " ⭐";
  return "";
}

export function isFeaturedColumn(index: number, total: number): boolean {
  return total >= 2 && index === Math.floor((total - 1) / 2);
}

export { channelFamilyLabel, groupPlansIntoChannelFamilies };
