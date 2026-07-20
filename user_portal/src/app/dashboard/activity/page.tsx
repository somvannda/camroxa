"use client";

import * as React from "react";
import { Search, X } from "lucide-react";

import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  EmptyPanel,
  PanelSection,
  SectionTitle,
  formatCreditValue,
  formatDateTime,
} from "@/components/dashboard/control-panel-ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  formatUsageTransactionLabel,
  resolveBillingMode,
  type BillingMode,
  type WalletTransaction,
} from "@/lib/credits";

function billingBadgeClass(mode: BillingMode): string {
  if (mode === "plan_allowance") return "bg-sky-500/15 text-sky-300 ring-sky-400/20";
  if (mode === "platform_absorb") return "bg-amber-500/15 text-amber-300 ring-amber-400/20";
  if (mode === "wallet") return "bg-rose-500/15 text-rose-300 ring-rose-400/20";
  return "bg-emerald-500/15 text-emerald-300 ring-emerald-400/20";
}

function amountClass(mode: BillingMode, direction: string): string {
  if (mode === "plan_allowance") return "text-sky-300";
  if (mode === "platform_absorb") return "text-amber-300";
  if (direction === "credit") return "text-emerald-300";
  return "text-rose-300";
}

function formatLedgerAmount(transaction: WalletTransaction, mode: BillingMode): string {
  if (mode === "plan_allowance" || mode === "platform_absorb") {
    return "0";
  }
  return `${transaction.direction === "credit" ? "+" : "−"}${formatCreditValue(transaction.amount)}`;
}

const BILLING_OPTIONS: Array<{ value: "all" | BillingMode; label: string; hint: string }> = [
  { value: "all", label: "All billing", hint: "Every ledger row" },
  { value: "plan_allowance", label: "Plan allowance", hint: "Covered by your subscription quota" },
  { value: "wallet", label: "Wallet credits", hint: "Charged from purchased credits" },
  { value: "platform_absorb", label: "Absorbed", hint: "Platform covered the cost" },
];

export default function DashboardActivityPage() {
  const { state } = useControlPanel();
  const [billingFilter, setBillingFilter] = React.useState<"all" | BillingMode>("all");
  const [search, setSearch] = React.useState("");

  const walletLoaded = state.wallet != null;
  const normalizedSearch = search.trim().toLowerCase();

  const recentTransactions = (state.wallet?.recent_transactions ?? []).filter((tx) => {
    if (billingFilter !== "all" && resolveBillingMode(tx) !== billingFilter) {
      return false;
    }
    if (!normalizedSearch) return true;
    const haystack = `${tx.purpose ?? ""} ${tx.reason ?? ""} ${formatUsageTransactionLabel(tx)}`.toLowerCase();
    return haystack.includes(normalizedSearch);
  });

  const activeBilling = BILLING_OPTIONS.find((option) => option.value === billingFilter) ?? BILLING_OPTIONS[0];

  return (
    <div className="grid gap-5">
      <SectionTitle
        title="Usage"
        description="Wallet and plan ledger for generation charges. Trends and activity live on Overview."
      />

      <PanelSection
        title="Find ledger rows"
        description="Filter by how the work was billed, or search by operation name."
      >
        <div className="grid gap-4">
          <div>
            <div className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
              Billing mode
            </div>
            <div className="flex flex-wrap gap-2">
              {BILLING_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setBillingFilter(option.value)}
                  className={`rounded-xl border px-3 py-2 text-left transition ${
                    billingFilter === option.value
                      ? "border-violet-400/40 bg-violet-500/15 text-white"
                      : "border-slate-700 bg-slate-950/40 text-slate-300 hover:border-slate-600 hover:bg-slate-900/60"
                  }`}
                >
                  <div className="text-sm font-medium">{option.label}</div>
                  <div className="mt-0.5 text-[11px] text-slate-500">{option.hint}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
              Search
            </div>
            <div className="relative max-w-xl">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search operation, reason, or billing label…"
                className="h-11 border-slate-700 bg-slate-950/50 pl-10 pr-10 text-slate-100 placeholder:text-slate-500"
              />
              {search ? (
                <button
                  type="button"
                  aria-label="Clear search"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  onClick={() => setSearch("")}
                >
                  <X className="h-4 w-4" />
                </button>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/40 px-3 py-2 text-xs text-slate-400">
            <span>
              Showing <span className="font-medium text-slate-200">{recentTransactions.length}</span> row
              {recentTransactions.length === 1 ? "" : "s"}
              {billingFilter !== "all" ? (
                <>
                  {" "}
                  · <span className="text-slate-300">{activeBilling.label}</span>
                </>
              ) : null}
              {normalizedSearch ? (
                <>
                  {" "}
                  · matching “<span className="text-slate-300">{search.trim()}</span>”
                </>
              ) : null}
            </span>
            {billingFilter !== "all" || search ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-8 text-slate-300"
                onClick={() => {
                  setBillingFilter("all");
                  setSearch("");
                }}
              >
                Clear filters
              </Button>
            ) : null}
          </div>
        </div>
      </PanelSection>

      <PanelSection title="Usage ledger" description="Plan allowance, wallet charges, and platform-absorbed rows.">
        {!walletLoaded ? (
          <EmptyPanel text="Unable to load usage history." />
        ) : recentTransactions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Operation</th>
                  <th className="px-3 py-2">Billing</th>
                  <th className="px-3 py-2">When</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {recentTransactions.map((transaction) => {
                  const mode = resolveBillingMode(transaction);
                  return (
                    <tr key={transaction.id} className="border-b border-slate-800/70">
                      <td className="px-3 py-2 text-slate-200">
                        {transaction.purpose || transaction.reason}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] ring-1 ${billingBadgeClass(mode)}`}
                        >
                          {formatUsageTransactionLabel(transaction)}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-400">{formatDateTime(transaction.created_at)}</td>
                      <td className={`px-3 py-2 text-right font-medium ${amountClass(mode, transaction.direction)}`}>
                        {formatLedgerAmount(transaction, mode)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyPanel text="No ledger rows match these filters." />
        )}
      </PanelSection>
    </div>
  );
}
