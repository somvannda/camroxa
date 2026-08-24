"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, CircleDollarSign, TicketPercent } from "lucide-react";

import { CreditsPanel } from "@/app/dashboard/credits/credits-panel";
import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  EmptyPanel,
  InlineBadge,
  PanelSection,
  PaymentRow,
  SectionTitle,
  StatTile,
  SummaryRow,
  formatCreditValue,
} from "@/components/dashboard/control-panel-ui";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { listBillingProviders, type BillingProviderConfig } from "@/lib/billing";
import { ProfileAddonPanel } from "@/components/dashboard/profile-addon-panel";

export default function DashboardBillingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { state, websiteBaseUrl } = useControlPanel();
  const activeTab = searchParams.get("tab") === "credits" ? "credits" : "subscription";
  const returnedPaymentId = searchParams.get("payment_id");
  const returnedPaymentStatus = searchParams.get("status");
  const [providerConfig, setProviderConfig] = React.useState<BillingProviderConfig | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    async function loadProviders() {
      try {
        const result = await listBillingProviders();
        if (!cancelled) {
          setProviderConfig(result);
        }
      } catch {
        if (!cancelled) {
          setProviderConfig(null);
        }
      }
    }

    void loadProviders();

    return () => {
      cancelled = true;
    };
  }, []);

  if (!state.user) {
    return null;
  }

  if (activeTab === "credits") {
    return (
      <div className="grid gap-5">
        <SectionTitle title="Billing" description="Subscription checkout, wallet credits, and payment history." />
        <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
          <Button type="button" variant="ghost" size="sm" onClick={() => router.replace("/dashboard/billing")}>
            Subscription
          </Button>
          <Button type="button" variant="default" size="sm">
            Credits
          </Button>
        </div>
        <CreditsPanel
          embedded
          returnedPaymentId={returnedPaymentId}
          returnedPaymentStatus={returnedPaymentStatus}
        />
      </div>
    );
  }

  const planLabel = state.user.plan_name ?? "No active subscription";
  const profileAllowance = state.user.profile_allowance ?? null;
  const quotaChannels =
    state.user.effective_quota_channels ??
    (profileAllowance != null ? profileAllowance + (state.user.profile_addon_slots ?? 0) : null);
  const creationLimit = state.user.effective_profile_allowance ?? profileAllowance;
  const recentPayments = state.payments.slice(0, 8);
  const paidPayments = state.payments.filter((payment) => payment.status.toLowerCase() === "paid");
  const pendingPayments = state.payments.filter((payment) => ["pending", "processing"].includes(payment.status.toLowerCase()));
  const totalSpendCents = paidPayments.reduce((sum, payment) => sum + payment.amount_cents, 0);
  const totalSavingsCents = paidPayments.reduce((sum, payment) => {
    const original = payment.original_amount_cents ?? payment.amount_cents;
    return sum + Math.max(original - payment.amount_cents, 0);
  }, 0);
  const latestPayment = recentPayments[0] ?? null;

  return (
    <div className="grid gap-5">
      <SectionTitle
        title="Billing"
        description="Subscription checkout, wallet credits, and payment history."
      />

      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
        <Button type="button" variant="default" size="sm">
          Subscription
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => router.replace("/dashboard/billing?tab=credits")}
        >
          Credits
        </Button>
      </div>

      <ProfileAddonPanel user={state.user} profileCount={state.profiles.length} />

      <div className="grid gap-3 md:grid-cols-3">
        <StatTile label="Paid checkouts" value={String(paidPayments.length)} hint="Successful payments on this account." />
        <StatTile label="Total spend" value={formatCurrency(totalSpendCents)} hint="Confirmed billing spend." />
        <StatTile
          label="Discount savings"
          value={formatCurrency(totalSavingsCents)}
          hint={`${pendingPayments.length} payment(s) pending.`}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(18,28,70,0.96),rgba(10,14,34,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.38)]">
          <CardHeader>
            <CardTitle className="font-display text-2xl text-white">Subscription status</CardTitle>
            <CardDescription className="text-slate-300/72">
              Current plan and credit wallet. Extra channel pairs are a separate product.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Active plan</div>
              <div className="mt-2 text-2xl font-semibold text-white">{planLabel}</div>
              <div className="mt-2 text-sm text-slate-300/72">
                {quotaChannels != null
                  ? `${state.profiles.length} profiles · cap ${creationLimit ?? quotaChannels} (max 10). Extra pairs do not multiply credits.`
                  : "No profile allowance data available yet."}
              </div>
            </div>
            <SummaryRow
              label="Profiles allocated"
              value={
                creationLimit != null
                  ? `${state.profiles.length} of ${creationLimit}`
                  : String(state.profiles.length)
              }
            />
            <SummaryRow
              label="Wallet credits"
              value={formatCreditValue(state.wallet?.balance ?? state.user.credit_balance ?? 0)}
            />
            <SummaryRow
              label="Checkout provider"
              value={providerConfig?.active_provider ?? "Not configured"}
            />
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button
                variant="outline"
                asChild
                className="border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06]"
              >
                <Link href={`${websiteBaseUrl}/pricing`}>
                  Compare plans
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button
                variant="outline"
                asChild
                className="border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06]"
              >
                <Link href="/onboarding/done">
                  Completion summary
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] shadow-[0_24px_80px_rgba(33,16,64,0.2)] ring-1 ring-white/6">
          <CardHeader>
            <CardTitle className="font-display text-2xl text-white">Recent checkout history</CardTitle>
            <CardDescription className="text-slate-300/72">
              Latest onboarding and billing payment records tied to your account.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {recentPayments.length > 0 ? (
              recentPayments.map((payment) => (
                <Link key={payment.id} href={`/dashboard/billing/${payment.id}`} className="block transition hover:-translate-y-0.5">
                  <PaymentRow payment={payment} />
                </Link>
              ))
            ) : (
              <EmptyPanel text="No billing payments recorded yet." />
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] shadow-[0_24px_80px_rgba(33,16,64,0.2)] ring-1 ring-white/6">
        <CardHeader>
          <CardTitle className="font-display text-2xl text-white">Billing management readiness</CardTitle>
          <CardDescription className="text-slate-300/72">
            Provider availability and checkout readiness for the next subscription action.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Paid checkout</div>
            <div className="mt-3 text-2xl font-semibold text-white">
              {providerConfig?.paid_checkout_available ? "Available" : "Limited"}
            </div>
            <div className="mt-2 text-sm text-slate-300/72">
              Live readiness for provider-backed subscription checkout.
            </div>
          </div>
          {(providerConfig?.providers ?? []).slice(0, 3).map((provider) => (
            <div key={provider.id} className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-medium text-white">{provider.label}</div>
                <InlineBadge text={provider.available ? "Available" : "Offline"} tone={provider.available ? "emerald" : "rose"} />
              </div>
              <div className="mt-2 text-sm text-slate-300/72">{provider.description}</div>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(340px,0.95fr)]">
        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] shadow-[0_24px_80px_rgba(33,16,64,0.2)] ring-1 ring-white/6">
          <CardHeader>
            <CardTitle className="font-display text-2xl text-white">Latest payment spotlight</CardTitle>
            <CardDescription className="text-slate-300/72">
              Detail view for the most recent billing record associated with this account.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {latestPayment ? (
              <>
                <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Plan</div>
                      <div className="mt-2 text-2xl font-semibold text-white">{latestPayment.plan_name}</div>
                    </div>
                    <div className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-slate-300">
                      {latestPayment.status}
                    </div>
                  </div>
                  <div className="mt-4 grid gap-3 text-sm text-slate-300/72">
                    <SummaryRow label="Amount" value={formatCurrency(latestPayment.amount_cents)} />
                    <SummaryRow label="Provider" value={latestPayment.provider || "Not available"} />
                    <SummaryRow label="Created" value={latestPayment.created_at} />
                    <SummaryRow label="Approved" value={latestPayment.approved_at ?? "Not approved yet"} />
                    <SummaryRow label="Fulfilled" value={latestPayment.fulfilled_at ?? "Not fulfilled yet"} />
                  </div>
                </div>
                {latestPayment.redeem_code ? (
                  <div className="rounded-[24px] border border-violet-400/25 bg-violet-500/[0.08] p-4 text-sm text-slate-200">
                    Redeem code applied: <span className="font-medium text-white">{latestPayment.redeem_code}</span>
                  </div>
                ) : null}
              </>
            ) : (
              <EmptyPanel text="No payment details are available yet." />
            )}
          </CardContent>
        </Card>

        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
          <CardHeader>
            <CardTitle className="font-display text-2xl text-white">Billing insights</CardTitle>
            <CardDescription className="text-slate-300/72">
              Quick interpretation of payment behavior, savings, and promo usage.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
              <div className="flex items-center gap-2 text-sm font-medium text-white">
                <CircleDollarSign className="h-4 w-4 text-emerald-200" />
                Spend pattern
              </div>
              <div className="mt-2 text-sm text-slate-300/72">
                {paidPayments.length > 0
                  ? `${paidPayments.length} paid transactions have been recorded so far.`
                  : "Paid billing history has not started yet."}
              </div>
            </div>
            <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
              <div className="flex items-center gap-2 text-sm font-medium text-white">
                <TicketPercent className="h-4 w-4 text-violet-200" />
                Promo usage
              </div>
              <div className="mt-2 text-sm text-slate-300/72">
                {totalSavingsCents > 0
                  ? `Discount and redeem pricing has saved ${formatCurrency(totalSavingsCents)} on completed payments.`
                  : "No completed discount savings have been recorded yet."}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
        <CardHeader>
          <CardTitle className="font-display text-2xl text-white">Billing actions</CardTitle>
          <CardDescription className="text-slate-300/72">
            Common next steps for subscription management and checkout planning.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Link
            href={`${websiteBaseUrl}/pricing`}
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-violet-400/25 hover:bg-violet-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">Compare plans</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Review Starter / Creator / Studio credit grants before changing plans.
            </div>
          </Link>
          <Link
            href="/dashboard/credits"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-emerald-400/25 hover:bg-emerald-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">Review credits</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Check wallet balance and redeem credit codes before your next purchase.
            </div>
          </Link>
          <Link
            href="/dashboard/activity"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-sky-400/25 hover:bg-sky-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">Usage ledger</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Review credit charges with your billing history.
            </div>
          </Link>
          <Link
            href="/dashboard/security"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-sky-400/25 hover:bg-sky-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">Update account</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Keep your account details current before making billing changes.
            </div>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

function formatCurrency(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}
