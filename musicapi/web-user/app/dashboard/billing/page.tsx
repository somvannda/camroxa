"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { apiFetch } from "@/lib/api";

interface Pack {
  id: string;
  amount: number;
  price: number;
  currency: string;
}

interface Billing {
  credits: number;
  packs: Pack[];
}

interface PricingRow {
  endpoint: string;
  model: string | null;
  credit_cost: number;
}

interface Checkout {
  transaction_id: string;
  reference_id: string;
  credits: number;
  currency: string;
  amount: number;
  qr: string | null;
  checkout_url: string | null;
  status: string;
  expires_at: string;
}

interface CheckoutStatus {
  status: "pending" | "paid" | "expired" | "failed" | string;
  paid_at: string | null;
}

const TERMINAL = new Set(["paid", "expired", "failed"]);

export default function BillingPage() {
  const [billing, setBilling] = useState<Billing | null>(null);
  const [pricing, setPricing] = useState<PricingRow[]>([]);
  const [error, setError] = useState("");

  const [startingId, setStartingId] = useState<string | null>(null);
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [status, setStatus] = useState<string>("pending");

  useEffect(() => {
    Promise.all([apiFetch<Billing>("/me/billing"), apiFetch<{ pricing: PricingRow[] }>("/pricing")])
      .then(([b, p]) => {
        setBilling(b);
        setPricing(p.pricing);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  async function startCheckout(pack: Pack) {
    setStartingId(pack.id);
    setError("");
    try {
      const tx = await apiFetch<Checkout>("/payments/champapay/create", {
        method: "POST",
        body: JSON.stringify({ pack_id: pack.id }),
      });
      setCheckout(tx);
      setStatus(tx.status || "pending");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start checkout");
    } finally {
      setStartingId(null);
    }
  }

  // Poll the gateway while the checkout modal is open, until it settles.
  useEffect(() => {
    const txId = checkout?.transaction_id;
    if (!txId) return;
    let stopped = false;
    const tick = async () => {
      try {
        const s = await apiFetch<CheckoutStatus>(`/payments/champapay/status/${txId}`);
        if (stopped) return;
        setStatus(s.status);
        if (s.status === "paid") {
          const b = await apiFetch<Billing>("/me/billing");
          if (!stopped) setBilling(b);
          stopped = true;
          clearInterval(timer);
        } else if (TERMINAL.has(s.status)) {
          stopped = true;
          clearInterval(timer);
        }
      } catch {
        /* transient error — keep polling */
      }
    };
    const timer = setInterval(tick, 3000);
    tick();
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [checkout?.transaction_id]);

  function closeCheckout() {
    setCheckout(null);
    setStatus("pending");
  }

  const settled = status === "paid";

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">Billing</h1>
      <p className="mt-1 text-sm text-white/50">Your credit balance and top-up packs.</p>

      {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}

      <div className="glass mt-6 rounded-2xl p-6">
        <div className="text-sm text-white/50">Current balance</div>
        <div className="mt-1 text-4xl font-extrabold text-[var(--emerald)]">{billing?.credits ?? 0} credits</div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {(billing?.packs ?? []).map((p) => (
          <div key={p.id} className="glass rounded-2xl p-6">
            <div className="text-2xl font-bold text-white">{p.amount}</div>
            <div className="text-sm text-white/50">credits</div>
            <div className="mt-4 text-lg font-semibold text-white">
              {p.currency} {p.price}
            </div>
            <button
              onClick={() => startCheckout(p)}
              disabled={startingId !== null}
              className="grad-bg mt-4 w-full rounded-lg py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {startingId === p.id ? "Starting…" : "Buy"}
            </button>
          </div>
        ))}
        {(!billing || billing.packs.length === 0) && (
          <div className="col-span-3 rounded-2xl border border-white/5 p-8 text-center text-sm text-white/50">No credit packs available yet.</div>
        )}
      </div>

      <div className="glass mt-6 rounded-2xl p-6">
        <h2 className="text-sm font-semibold text-white/50">API endpoint costs</h2>
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-white/50">
              <th className="pb-2">Endpoint</th>
              <th className="pb-2">Model</th>
              <th className="pb-2">Credits</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {pricing.map((p, i) => (
              <tr key={i} className="border-t border-white/5">
                <td className="py-2 font-mono text-xs text-white">/v1/{p.endpoint}</td>
                <td className="py-2 text-white/50">{p.model ?? "—"}</td>
                <td className="py-2 text-white">{p.credit_cost}</td>
                <td className="py-2 text-right">
                  <Link href="/docs" className="text-xs text-[var(--violet)] hover:underline">view docs</Link>
                </td>
              </tr>
            ))}
            {pricing.length === 0 && (
              <tr>
                <td colSpan={4} className="py-4 text-center text-white/50">No pricing configured.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {checkout && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={closeCheckout}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="glass relative w-full max-w-sm rounded-2xl p-6"
          >
            <button
              type="button"
              onClick={closeCheckout}
              aria-label="Close"
              className="absolute right-3 top-3 inline-flex h-8 w-8 items-center justify-center rounded-lg text-white/50 hover:bg-white/10 hover:text-white"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>

            <h2 className="text-lg font-bold text-white">Top up {checkout.credits} credits</h2>
            <p className="mt-1 text-sm text-white/50">
              Pay USD {checkout.amount.toFixed(2)} via ABA PayWay / KHQR
            </p>

            {settled ? (
              <div className="mt-6 rounded-xl border border-[var(--emerald)]/30 bg-[var(--emerald)]/10 p-6 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[var(--emerald)]/20 text-[var(--emerald)]">
                  <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                </div>
                <div className="mt-3 font-semibold text-white">Payment received</div>
                <div className="text-sm text-[var(--emerald)]">Credits added to your account</div>
              </div>
            ) : (
              <>
                {checkout.qr && (
                  <div className="mt-5 flex justify-center">
                    <div className="rounded-xl bg-white p-3">
                      <QRCodeSVG value={checkout.qr} size={196} level="M" />
                    </div>
                  </div>
                )}

                {checkout.checkout_url && (
                  <a
                    href={checkout.checkout_url}
                    target="_blank"
                    rel="noreferrer"
                    className="grad-bg mt-4 block w-full rounded-lg py-2 text-center text-sm font-semibold text-white"
                  >
                    Open payment page
                  </a>
                )}

                <div className="mt-4 text-center text-sm text-white/60">
                  {status === "expired" ? (
                    <span className="text-amber-300">This QR code expired. Please start again.</span>
                  ) : status === "failed" ? (
                    <span className="text-red-300">Payment failed. Please try again.</span>
                  ) : (
                    <span className="inline-flex items-center gap-2">
                      <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--emerald)]" />
                      Waiting for payment…
                    </span>
                  )}
                </div>
              </>
            )}

            <div className="mt-4 text-center font-mono text-[10px] text-white/30">
              {checkout.reference_id}
            </div>

            <button
              onClick={closeCheckout}
              className="mt-2 w-full rounded-lg border border-white/10 py-2 text-sm font-medium text-white/80 hover:bg-white/5"
            >
              {settled ? "Done" : "Close"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
