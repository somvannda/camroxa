"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import { fetchTopupStatus, type TopupStatus } from "@/lib/checkout-api";

const PAYMENT_KEY = "camxora:checkout-payment";

export function CheckoutView() {
  const params = useSearchParams();
  const { refresh } = useAuth();
  const [paymentId, setPaymentId] = useState(params.get("payment_id") ?? "");
  const [status, setStatus] = useState<TopupStatus | null>(null);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(Boolean(paymentId));

  useEffect(() => {
    if (paymentId) return;
    const saved = window.sessionStorage.getItem(PAYMENT_KEY);
    if (saved) {
      setPaymentId(saved);
      setChecking(true);
    }
  }, [paymentId]);

  useEffect(() => {
    if (!paymentId) return;
    let active = true;
    let timer: number | undefined;
    let attempts = 0;

    const check = async () => {
      try {
        const next = await fetchTopupStatus(paymentId);
        if (!active) return;
        setStatus(next);
        setChecking(false);
        if (next.fulfilled) {
          window.sessionStorage.removeItem(PAYMENT_KEY);
          await refresh();
          return;
        }
        if (next.status === "failed" || next.status === "expired") return;
        attempts += 1;
        if (attempts < 100) {
          timer = window.setTimeout(check, 3000);
        } else {
          setError("Payment is still pending. Check your email or contact support.");
        }
      } catch (cause) {
        if (!active) return;
        setChecking(false);
        setError(cause instanceof Error ? cause.message : "Could not check payment");
      }
    };

    void check();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [paymentId, refresh]);

  if (!paymentId) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-credit-card" /></span>
          <h1>No checkout in progress</h1>
          <p>Choose a credit pack to start a secure checkout.</p>
          <Link className="btn btn-primary" href="/pricing">View credit packs</Link>
        </div>
      </div>
    );
  }

  if (checking && !status) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-spinner" /></span>
          <h1>Checking your payment…</h1>
          <p>Keep this page open while we confirm the transaction.</p>
        </div>
      </div>
    );
  }

  if (status?.fulfilled) {
    return (
      <div className="page">
        <div className="checkout-result panel">
          <span className="checkout-result-icon success"><Icon name="fa-check" /></span>
          <div className="eyebrow">Payment complete</div>
          <h1>{status.credits.toLocaleString()} credits added.</h1>
          <p>
            Your {status.pack_name || "credit pack"} is now in your balance. Start
            creating whenever you are ready.
          </p>
          <div className="page-actions">
            <Link className="btn btn-primary" href="/create">Create music</Link>
            <Link className="btn btn-ghost" href="/pricing">Buy another pack</Link>
          </div>
        </div>
      </div>
    );
  }

  if (status && (status.status === "failed" || status.status === "expired")) {
    return (
      <div className="page">
        <div className="checkout-result panel">
          <span className="checkout-result-icon failed"><Icon name="fa-xmark" /></span>
          <div className="eyebrow">Checkout {status.status}</div>
          <h1>Payment was not completed.</h1>
          <p>No credits were added. You can start a new checkout whenever you are ready.</p>
          <div className="page-actions">
            <Link className="btn btn-primary" href="/pricing">Try again</Link>
            <Link className="btn btn-ghost" href="/support">Contact support</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="checkout-result panel">
        <span className="checkout-result-icon pending"><Icon name="fa-clock" /></span>
        <div className="eyebrow">Payment pending</div>
        <h1>Waiting for confirmation.</h1>
        <p>
          We’re checking with the payment provider. Keep this page open — the credits
          will appear automatically.
        </p>
        {error ? <p className="fine" style={{ color: "#f87171" }}>{error}</p> : null}
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/pricing">Back to pricing</Link>
          <Link className="btn btn-ghost" href="/support">Need help?</Link>
        </div>
      </div>
    </div>
  );
}
