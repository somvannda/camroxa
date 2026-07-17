"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, CircleDollarSign, CreditCard, TicketPercent } from "lucide-react";

import {
  EmptyPanel,
  SectionTitle,
  SummaryRow,
  formatDateTime,
  formatMoney,
} from "@/components/dashboard/control-panel-ui";
import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getBillingPayment, type BillingPayment } from "@/lib/billing";

export default function DashboardBillingDetailPage() {
  const params = useParams<{ paymentId: string }>();
  const { state, websiteBaseUrl } = useControlPanel();
  const paymentId = String(params?.paymentId ?? "");
  const existingPayment = state.payments.find((payment) => payment.id === paymentId) ?? null;
  const [payment, setPayment] = React.useState<BillingPayment | null>(existingPayment);
  const [loading, setLoading] = React.useState(!existingPayment);

  React.useEffect(() => {
    let cancelled = false;

    async function loadPayment() {
      if (existingPayment || !paymentId) return;
      try {
        const nextPayment = await getBillingPayment(paymentId);
        if (!cancelled) {
          setPayment(nextPayment);
        }
      } catch {
        if (!cancelled) {
          setPayment(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadPayment();

    return () => {
      cancelled = true;
    };
  }, [existingPayment, paymentId]);

  React.useEffect(() => {
    if (existingPayment) {
      setPayment(existingPayment);
      setLoading(false);
    }
  }, [existingPayment]);

  if (loading) {
    return (
      <div className="grid gap-6">
        <SectionTitle
          title="Payment Detail"
          description="Loading your billing record."
        />
        <EmptyPanel text="Loading payment details..." />
      </div>
    );
  }

  if (!payment) {
    return (
      <div className="grid gap-6">
        <SectionTitle
          title="Payment Detail"
          description="This billing record could not be found in the current account context."
        />
        <EmptyPanel text="The requested payment is not available. Return to billing and choose another record." />
      </div>
    );
  }

  const discountSavings =
    payment.original_amount_cents !== null && payment.original_amount_cents !== undefined
      ? Math.max(payment.original_amount_cents - payment.amount_cents, 0)
      : 0;

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle
          title="Payment Detail"
          description="Inspect the selected billing record, payment status, and pricing breakdown."
        />
        <Button
          variant="outline"
          asChild
          className="border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06]"
        >
          <Link href="/dashboard/billing">
            <ArrowLeft className="h-4 w-4" />
            Back to billing
          </Link>
        </Button>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(340px,0.9fr)_minmax(0,1.1fr)]">
        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(18,28,70,0.96),rgba(10,14,34,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.38)]">
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle className="font-display text-2xl text-white">{payment.plan_name}</CardTitle>
                <CardDescription className="text-slate-300/72">
                  Detailed checkout and fulfillment state for this subscription payment.
                </CardDescription>
              </div>
              <div className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-slate-300">
                {payment.status}
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm text-slate-300/72">
            <SummaryRow label="Amount paid" value={formatMoney(payment.amount_cents)} />
            <SummaryRow label="Currency" value={payment.currency} />
            <SummaryRow label="Provider" value={payment.provider || "Not available"} />
            <SummaryRow label="External payment ID" value={payment.external_payment_id || "Not available"} />
            <SummaryRow label="Created" value={formatDateTime(payment.created_at)} />
            <SummaryRow label="Approved" value={formatDateTime(payment.approved_at)} />
            <SummaryRow label="Fulfilled" value={formatDateTime(payment.fulfilled_at)} />
            <SummaryRow label="Updated" value={formatDateTime(payment.updated_at)} />
          </CardContent>
        </Card>

        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] shadow-[0_24px_80px_rgba(33,16,64,0.2)] ring-1 ring-white/6">
          <CardHeader>
            <CardTitle className="font-display text-2xl text-white">Pricing breakdown</CardTitle>
            <CardDescription className="text-slate-300/72">
              Visibility into original amount, final amount, and any redeem-driven savings.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                <div className="flex items-center gap-2 text-sm font-medium text-white">
                  <CircleDollarSign className="h-4 w-4 text-emerald-200" />
                  Final amount
                </div>
                <div className="mt-3 text-2xl font-semibold text-white">{formatMoney(payment.amount_cents)}</div>
              </div>
              <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                <div className="flex items-center gap-2 text-sm font-medium text-white">
                  <CreditCard className="h-4 w-4 text-sky-200" />
                  Original amount
                </div>
                <div className="mt-3 text-2xl font-semibold text-white">
                  {formatMoney(payment.original_amount_cents ?? payment.amount_cents)}
                </div>
              </div>
              <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                <div className="flex items-center gap-2 text-sm font-medium text-white">
                  <TicketPercent className="h-4 w-4 text-violet-200" />
                  Savings
                </div>
                <div className="mt-3 text-2xl font-semibold text-white">{formatMoney(discountSavings)}</div>
              </div>
            </div>

            <div className="grid gap-3 rounded-[24px] border border-white/10 bg-white/[0.03] p-5 text-sm text-slate-300/72">
              <SummaryRow label="Redeem code" value={payment.redeem_code ?? "No redeem code applied"} />
              <SummaryRow label="Checkout URL" value={payment.checkout_url || "Not available"} />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
        <CardHeader>
          <CardTitle className="font-display text-2xl text-white">Billing actions</CardTitle>
          <CardDescription className="text-slate-300/72">
            Related next steps for subscription management and future checkout decisions.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Link
            href="/dashboard/billing"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-violet-400/25 hover:bg-violet-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">View all payments</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Return to the billing page and review all recent account checkout records.
            </div>
          </Link>
          <Link
            href={`${websiteBaseUrl}/pricing`}
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-emerald-400/25 hover:bg-emerald-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">Compare plans</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Review pricing and allowance before choosing a different subscription tier.
            </div>
          </Link>
          <Link
            href="/dashboard/credits"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-sky-400/25 hover:bg-sky-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">Review credits</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Check wallet balance and redeem codes before your next purchase or promo redemption.
            </div>
          </Link>
          <Link
            href="/dashboard/activity"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-emerald-400/25 hover:bg-emerald-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">Usage ledger</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Compare plan allowance vs credits charged with this billing record.
            </div>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
