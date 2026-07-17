"use client";

import * as React from "react";
import Link from "next/link";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PublicPlan } from "@/lib/billing";
import {
  billingPriceLabel,
  planForFamilyTerm,
  type BillingTermKey,
  type ChannelPlanFamily,
} from "@/lib/plan-channel-families";
import {
  buildComparisonSections,
  channelFamilyLabel,
  groupPlansIntoChannelFamilies,
  isFeaturedColumn,
  planBadge,
  type CellValue,
  type ComparisonRow,
} from "@/lib/plan-comparison";
import { type PlanTermDiscounts } from "@/lib/plan-pricing";

type OnboardingPlanPickerProps = {
  plans: PublicPlan[];
  termDiscounts: PlanTermDiscounts;
  pricingPageUrl: string;
  paidCheckoutAvailable: boolean;
  creatingPayment: boolean;
  selectedPlanId: string | null;
  onSelectPlan: (planId: string) => void;
};

function billingTermForRowLabel(label: string): BillingTermKey | null {
  if (label === "Monthly") return "monthly";
  if (label.startsWith("6 Months")) return "semiAnnual";
  if (label.startsWith("Annual")) return "annual";
  return null;
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
      className={cn("min-w-[140px] px-4 py-4 text-left align-bottom", featured && "bg-white/[0.04]")}
    >
      <div className={cn("text-sm font-semibold", featured ? "text-white" : "text-slate-100")}>
        {channelFamilyLabel(family.channels)}
        {planBadge(index, total)}
      </div>
      {discounted ? (
        <div className="mt-1 text-xs text-fuchsia-200/90">Launch offer active</div>
      ) : null}
    </th>
  );
}

function SectionHeaderRow({ title, families }: { title: string; families: ChannelPlanFamily[] }) {
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
          className={cn(
            "px-4 py-3 text-left text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400/75",
            isFeaturedColumn(index, families.length) && "bg-white/[0.03]",
          )}
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
        className={cn(
          "sticky left-0 z-10 bg-[#0b1020]/95 px-4 py-3 text-left font-normal text-slate-300/88 backdrop-blur",
          row.emphasized && "font-medium text-white",
        )}
      >
        {row.label}
      </th>
      {row.values.slice(0, planCount).map((cell, index) => (
        <td
          key={`${row.label}-${index}`}
          className={cn(
            "px-4 py-3",
            index === featuredIndex && "bg-white/[0.03] font-medium text-white",
          )}
        >
          <ComparisonCell cell={cell} />
        </td>
      ))}
    </tr>
  );
}

function BillingCheckoutRow({
  row,
  families,
  termDiscounts,
  featuredIndex,
  paidCheckoutAvailable,
  creatingPayment,
  selectedPlanId,
  onSelectPlan,
}: {
  row: ComparisonRow;
  families: ChannelPlanFamily[];
  termDiscounts: PlanTermDiscounts;
  featuredIndex: number;
  paidCheckoutAvailable: boolean;
  creatingPayment: boolean;
  selectedPlanId: string | null;
  onSelectPlan: (planId: string) => void;
}) {
  const billingTerm = billingTermForRowLabel(row.label);

  return (
    <tr className="border-t border-white/6 text-sm text-slate-200/82">
      <th
        scope="row"
        className="sticky left-0 z-10 bg-[#0b1020]/95 px-4 py-3 text-left font-medium text-white backdrop-blur"
      >
        {row.label}
      </th>
      {families.map((family, index) => {
        const plan = billingTerm ? planForFamilyTerm(family, billingTerm) : null;
        const priceLabel = billingTerm ? billingPriceLabel(family, billingTerm, termDiscounts) : "—";
        const featured = index === featuredIndex;
        const loading = Boolean(plan && creatingPayment && selectedPlanId === plan.id);

        return (
          <td
            key={`${row.label}-${family.channels}`}
            className={cn("px-4 py-4 align-top", featured && "bg-white/[0.03]")}
          >
            <div className="grid gap-3">
              <div className={cn("text-base font-semibold", featured && "text-white")}>{priceLabel}</div>
              <Button
                type="button"
                size="sm"
                className="w-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-[0_12px_28px_rgba(118,77,255,0.22)] hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
                onClick={() => plan && onSelectPlan(plan.id)}
                disabled={!paidCheckoutAvailable || !plan || creatingPayment}
              >
                {loading
                  ? "Starting checkout..."
                  : paidCheckoutAvailable
                    ? "Continue"
                    : "Unavailable"}
              </Button>
            </div>
          </td>
        );
      })}
    </tr>
  );
}

function PricingNotes({ plans }: { plans: PublicPlan[] }) {
  const offers = plans.filter((plan) => plan.offer);

  return (
    <div className="border-t border-white/8 px-4 py-5 md:px-6">
      <p className="text-sm leading-6 text-slate-300/72">
        Compare plans the same way as the public pricing page. Choose a channel count and billing term
        in the Billing section to continue to KHQR checkout.
      </p>

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

export function OnboardingPlanPicker({
  plans,
  termDiscounts,
  pricingPageUrl,
  paidCheckoutAvailable,
  creatingPayment,
  selectedPlanId,
  onSelectPlan,
}: OnboardingPlanPickerProps) {
  const families = React.useMemo(() => groupPlansIntoChannelFamilies(plans), [plans]);

  if (families.length === 0) {
    return (
      <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6 text-sm text-slate-200/72">
        No subscription plans are available right now. Please try again later or contact support.
      </div>
    );
  }

  const sections = buildComparisonSections(families, termDiscounts);
  const featuredIndex = Math.floor((families.length - 1) / 2);

  return (
    <div className="grid gap-4">
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
                ...section.rows.map((row) =>
                  section.title === "Billing" ? (
                    <BillingCheckoutRow
                      key={`${section.title}-${row.label}`}
                      row={row}
                      families={families}
                      termDiscounts={termDiscounts}
                      featuredIndex={featuredIndex}
                      paidCheckoutAvailable={paidCheckoutAvailable}
                      creatingPayment={creatingPayment}
                      selectedPlanId={selectedPlanId}
                      onSelectPlan={onSelectPlan}
                    />
                  ) : (
                    <ComparisonDataRow
                      key={`${section.title}-${row.label}`}
                      row={row}
                      planCount={families.length}
                      featuredIndex={featuredIndex}
                    />
                  ),
                ),
              ])}
            </tbody>
          </table>
        </div>

        <PricingNotes plans={plans} />
      </div>

      <div className="text-center text-sm text-slate-300/72">
        Same plan data as{" "}
        <Link
          href={pricingPageUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-white underline-offset-4 hover:underline"
        >
          the public pricing page
        </Link>
        .
      </div>
    </div>
  );
}
