"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, CircleOff, Clock3, LoaderCircle } from "lucide-react";

import { completeMockPayment, getBillingPayment, type BillingPayment } from "@/lib/billing";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";

function formatUsd(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);
}

export default function MockCheckoutPage() {
  return (
    <React.Suspense fallback={null}>
      <MockCheckoutContent />
    </React.Suspense>
  );
}

function MockCheckoutContent() {
  const params = useParams<{ paymentId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const addonMode = searchParams.get("mode") === "addon";
  const paymentId = String(params?.paymentId ?? "");

  const [payment, setPayment] = React.useState<BillingPayment | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [submitting, setSubmitting] = React.useState<"" | "paid" | "failed" | "expired">("");
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!paymentId) return;

    let cancelled = false;
    setLoading(true);
    setError("");

    getBillingPayment(paymentId)
      .then((result) => {
        if (!cancelled) {
          setPayment(result);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load mock checkout.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [paymentId]);

  async function handleComplete(status: "paid" | "failed" | "expired") {
    if (!paymentId) return;

    setSubmitting(status);
    setError("");
    try {
      const updated = await completeMockPayment(paymentId, status);
      setPayment(updated);
      router.replace(
        addonMode
          ? `/onboarding?mode=addon&payment_id=${paymentId}`
          : `/onboarding?payment_id=${paymentId}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update mock payment.");
    } finally {
      setSubmitting("");
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-6 py-12">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(1000px_circle_at_30%_15%,hsl(var(--primary)/0.18),transparent_52%),radial-gradient(900px_circle_at_75%_80%,hsl(217_90%_68%/0.14),transparent_62%)]" />
      </div>

      <Card className="relative w-full max-w-2xl border-border/70 bg-card/90 backdrop-blur supports-[backdrop-filter]:bg-card/75">
        <CardHeader className="space-y-3">
          <div className="text-xs uppercase tracking-[0.25em] text-primary">Development Checkout</div>
          <div className="font-display text-3xl font-semibold tracking-tight text-white">
            Mock payment for CAMXORA
          </div>
          <div className="text-sm text-muted-foreground">
            This is a local development checkout. Use it to simulate paid, failed, or expired outcomes before
            switching the provider to CutLuy in production.
          </div>
        </CardHeader>

        <CardContent className="grid gap-4">
          {loading ? (
            <div className="flex min-h-40 items-center justify-center gap-3 text-sm text-muted-foreground">
              <LoaderCircle className="h-5 w-5 animate-spin text-primary" />
              Loading payment...
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-100">
              {error}
            </div>
          ) : payment ? (
            <>
              <div className="grid gap-4 rounded-2xl border border-white/10 bg-background/30 p-5 md:grid-cols-2">
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-300/60">Plan</div>
                  <div className="mt-2 text-lg font-semibold text-white">{payment.plan_name}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-300/60">Amount</div>
                  <div className="mt-2 text-lg font-semibold text-white">{formatUsd(payment.amount_cents)}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-300/60">Provider</div>
                  <div className="mt-2 text-sm font-medium text-white">{payment.provider}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-[0.2em] text-slate-300/60">Status</div>
                  <div className="mt-2 text-sm font-medium text-white">{payment.status}</div>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <Button
                  type="button"
                  onClick={() => void handleComplete("paid")}
                  disabled={Boolean(submitting) || payment.status === "paid"}
                  className="w-full"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  {submitting === "paid" ? "Processing..." : "Mark Paid"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleComplete("failed")}
                  disabled={Boolean(submitting) || payment.status === "failed"}
                  className="w-full"
                >
                  <CircleOff className="h-4 w-4" />
                  {submitting === "failed" ? "Processing..." : "Mark Failed"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleComplete("expired")}
                  disabled={Boolean(submitting) || payment.status === "expired"}
                  className="w-full"
                >
                  <Clock3 className="h-4 w-4" />
                  {submitting === "expired" ? "Processing..." : "Mark Expired"}
                </Button>
              </div>

              <div className="rounded-xl border border-white/10 bg-background/30 p-4 text-sm text-slate-200/75">
                After you choose a payment result, CAMXORA returns to onboarding, verifies the payment on the
                server, and continues automatically.
              </div>
            </>
          ) : null}
        </CardContent>

        <CardFooter className="flex flex-wrap items-center justify-between gap-3">
          <Link className="text-sm text-muted-foreground underline-offset-4 hover:underline" href="/onboarding">
            Back to onboarding
          </Link>
          <div className="text-xs text-muted-foreground">Recommended production checkout: `account.camxora.com/checkout`</div>
        </CardFooter>
      </Card>
    </div>
  );
}
