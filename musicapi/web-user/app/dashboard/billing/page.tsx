"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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
  checkout_url: string | null;
}

export default function BillingPage() {
  const [billing, setBilling] = useState<Billing | null>(null);
  const [pricing, setPricing] = useState<PricingRow[]>([]);
  const [error, setError] = useState("");
  const [busyPackId, setBusyPackId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([apiFetch<Billing>("/me/billing"), apiFetch<{ pricing: PricingRow[] }>("/pricing")])
      .then(([b, p]) => {
        setBilling(b);
        setPricing(p.pricing);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  async function buy(pack: Pack) {
    setError("");
    setBusyPackId(pack.id);
    try {
      const checkout = await apiFetch<Checkout>("/payments/chmaba/create", {
        method: "POST",
        body: JSON.stringify({ pack_id: pack.id }),
      });
      if (checkout.checkout_url) {
        window.location.href = checkout.checkout_url;
        return;
      }
      setError("Checkout could not be started. Please try again.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setBusyPackId(null);
    }
  }

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
              className="grad-bg mt-4 w-full rounded-lg py-2 text-sm font-semibold text-white disabled:opacity-60"
              onClick={() => buy(p)}
              disabled={busyPackId !== null}
            >
              {busyPackId === p.id ? "Starting…" : "Buy"}
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

      <p className="mt-4 text-xs text-white/50">Payments are processed securely by ChmabaPay (KHQR / ABA PayWay). Credits are added to your account once payment is confirmed.</p>
    </div>
  );
}
