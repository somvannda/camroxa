"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { KhqrModal } from "@/components/billing/khqr-modal";

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

interface PromoQuote {
  code: string;
  kind: string;
  value: number;
  amount: number;
  credits: number;
  discount: number;
}

interface Checkout {
  transaction_id: string;
  credits: number;
  currency: string;
  amount: number;
  qr_url: string | null;
  checkout_url: string | null;
  expires_at: string | null;
}

interface Tx {
  id: string;
  credit_amount: number;
  currency: string;
  amount: number;
  payment_method: string;
  status: string;
  bill_number: string | null;
  paid_at: string | null;
  created_at: string;
}

function formatDateTime(s: string): string {
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function statusChip(status: string): React.ReactNode {
  const s = (status || "").toLowerCase();
  const tone =
    s === "paid" || s === "completed" || s === "success"
      ? "border-[var(--emerald)]/30 bg-[var(--emerald)]/10 text-[var(--emerald)]"
      : s === "failed" || s === "expired" || s === "cancelled"
        ? "border-red-500/25 bg-red-500/10 text-red-300"
        : "border-white/10 bg-white/[0.04] text-white/60";
  return (
    <span className={`inline-flex rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${tone}`}>
      {s || "pending"}
    </span>
  );
}

function csvCell(v: unknown): string {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export default function BillingPage() {
  const [billing, setBilling] = useState<Billing | null>(null);
  const [pricing, setPricing] = useState<PricingRow[]>([]);
  const [transactions, setTransactions] = useState<Tx[]>([]);
  const [error, setError] = useState("");
  const [busyPackId, setBusyPackId] = useState<string | null>(null);
  const [checkout, setCheckout] = useState<Checkout | null>(null);

  // One validated quote per pack: a percent code changes the price of every
  // pack, a bonus code adds the same credits to each, so both are previewed per
  // card. The code is re-validated server-side at checkout.
  const [promoInput, setPromoInput] = useState("");
  const [promoApplied, setPromoApplied] = useState<{ code: string; kind: string; value: number } | null>(null);
  const [quotes, setQuotes] = useState<Record<string, PromoQuote>>({});
  const [promoBusy, setPromoBusy] = useState(false);
  const [promoError, setPromoError] = useState("");

  const load = useCallback(() => {
    Promise.all([
      apiFetch<Billing>("/me/billing"),
      apiFetch<{ pricing: PricingRow[] }>("/pricing"),
      apiFetch<Tx[]>("/me/transactions").catch(() => [] as Tx[]),
    ])
      .then(([b, p, t]) => {
        setBilling(b);
        setPricing(p.pricing);
        setTransactions(t);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Same cheapest-active-pack rate /me/usage uses, so the displayed value agrees.
  const creditValue = useMemo(() => {
    const packs = [...(billing?.packs ?? [])].sort((a, b) => a.amount - b.amount);
    const cheapest = packs[0];
    if (!cheapest || cheapest.amount <= 0 || cheapest.price <= 0) return 0.005;
    return cheapest.price / cheapest.amount;
  }, [billing]);

  function exportHistory() {
    const header = ["DateTime", "Credits", "Amount", "Status", "Bill Number"];
    const lines = [header.map(csvCell).join(",")];
    for (const t of transactions) {
      lines.push(
        [
          formatDateTime(t.paid_at || t.created_at),
          String(t.credit_amount ?? 0),
          `${t.currency || ""} ${t.amount ?? 0}`.trim(),
          t.status || "",
          t.bill_number || "",
        ]
          .map(csvCell)
          .join(","),
      );
    }
    const blob = new Blob([`\uFEFF${lines.join("\n")}`], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "billing_history.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Revoke on the next tick so the browser has started the download.
    window.setTimeout(() => window.URL.revokeObjectURL(url), 0);
  }

  async function buy(pack: Pack) {
    setError("");
    setBusyPackId(pack.id);
    try {
      const session = await apiFetch<Checkout>("/payments/chmaba/create", {
        method: "POST",
        body: JSON.stringify({
          pack_id: pack.id,
          ...(promoApplied ? { promo_code: promoApplied.code } : {}),
        }),
      });
      if (session.qr_url) {
        setCheckout(session);
        return;
      }
      // No inline QR from the provider — fall back to the hosted checkout.
      if (session.checkout_url) {
        window.location.assign(session.checkout_url);
        return;
      }
      setError("Checkout could not be started. Please try again.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setBusyPackId(null);
    }
  }

  /**
   * Preview a code against every active pack. The server answers per pack
   * because a percent discount scales with price while a bonus is fixed; both
   * kinds therefore render on their own card. Checkout recomputes the charge,
   * so this preview can never reduce what is actually billed.
   */
  async function applyPromo() {
    const code = promoInput.trim();
    if (!code) return;
    const packs = billing?.packs ?? [];
    if (packs.length === 0) {
      setPromoError("Packs have not loaded yet — try again in a moment.");
      return;
    }
    setPromoBusy(true);
    setPromoError("");
    try {
      const validated = await Promise.all(
        packs.map((p) =>
          apiFetch<PromoQuote>("/me/promo/validate", {
            method: "POST",
            body: JSON.stringify({ code, pack_id: p.id }),
          }),
        ),
      );
      const next: Record<string, PromoQuote> = {};
      validated.forEach((q, i) => {
        next[packs[i].id] = q;
      });
      const first = validated[0];
      setQuotes(next);
      setPromoApplied({
        code: first?.code ?? code.toUpperCase(),
        kind: first?.kind ?? "",
        value: first?.value ?? 0,
      });
      setPromoInput(first?.code ?? code.toUpperCase());
    } catch (e) {
      setPromoApplied(null);
      setQuotes({});
      setPromoError(e instanceof Error ? e.message : "That code could not be applied.");
    } finally {
      setPromoBusy(false);
    }
  }

  function removePromo() {
    setPromoApplied(null);
    setQuotes({});
    setPromoInput("");
    setPromoError("");
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">Billing</h1>
      <p className="mt-1 text-sm text-white/50">Manage payment details</p>

      {error && <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</div>}

      {/* Balance information */}
      <div className="glass mt-6 rounded-2xl p-6">
        <div className="text-sm text-white/50">Balance Information</div>
        <div className="mt-1 text-4xl font-extrabold text-[var(--emerald)]">
          {billing?.credits ?? 0} <span className="text-lg font-semibold text-white/60">credits</span>
        </div>
        <ul className="mt-4 space-y-1.5 text-xs text-white/50">
          <li>Credits never expire and can be used anytime</li>
          <li>Rate limit: 20 request/10second (20 req/10s)</li>
          <li>Each credit is valued at ${creditValue.toFixed(4)} USD.</li>
        </ul>
      </div>

      {/* Add credits */}
      <div className="glass mt-6 rounded-2xl p-6">
        <h2 className="text-lg font-semibold text-white">Add Credits</h2>
        <p className="mt-1 text-sm text-white/50">Buy credits before you integrate. Top up any time.</p>

        {/* Optional checkout code: a percent discount or bonus credits on a pack. */}
        <div className="mt-5 rounded-xl border border-white/10 bg-white/[0.02] p-4">
          <label
            htmlFor="promo-code"
            className="text-xs font-semibold uppercase tracking-wide text-white/50"
          >
            Promo code
          </label>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            <input
              id="promo-code"
              value={promoInput}
              onChange={(e) => setPromoInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => {
                if (e.key === "Enter") void applyPromo();
              }}
              placeholder="CAMX-XXXXXX"
              autoComplete="off"
              spellCheck={false}
              disabled={promoApplied !== null}
              className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-mono text-sm uppercase text-white placeholder:text-white/25 outline-none focus:border-[var(--violet)]/60 disabled:opacity-60"
            />
            {promoApplied ? (
              <button
                type="button"
                onClick={removePromo}
                className="inline-flex items-center justify-center rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-white/80 transition hover:bg-white/10"
              >
                Remove
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void applyPromo()}
                disabled={promoBusy || !promoInput.trim()}
                className="inline-flex items-center justify-center rounded-lg border border-white/10 bg-white/[0.06] px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10 disabled:opacity-40"
              >
                {promoBusy ? "Checking…" : "Apply"}
              </button>
            )}
          </div>
          {promoError && <p className="mt-2 text-xs text-red-300">{promoError}</p>}
          {promoApplied && (
            <p className="mt-2 text-xs text-[var(--emerald)]">
              {promoApplied.kind === "percent"
                ? `${promoApplied.value}% off applied — pack prices below are updated.`
                : `+${promoApplied.value.toLocaleString()} bonus credits applied to any pack.`}
            </p>
          )}
          <p className="mt-2 text-xs text-white/35">
            Code that grants credits without a purchase? Redeem it on the{" "}
            <Link href="/dashboard/redeem" className="text-[var(--violet)] hover:underline">
              Redeem page
            </Link>
            .
          </p>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {(billing?.packs ?? []).map((p) => {
            const quote = promoApplied ? quotes[p.id] : undefined;
            const bonus = quote ? Math.max(0, quote.credits - p.amount) : 0;
            return (
              <div key={p.id} className="rounded-xl border border-white/10 bg-white/[0.02] p-5">
                <div className="text-2xl font-bold text-white">{p.amount.toLocaleString()}</div>
                <div className="text-sm text-white/50">credits</div>
                {bonus > 0 && (
                  <div className="mt-0.5 text-xs font-semibold text-[var(--emerald)]">
                    +{bonus.toLocaleString()} bonus
                  </div>
                )}
                <div className="mt-4 text-lg font-semibold text-white">
                  {quote ? (
                    <>
                      <span className="mr-2 text-sm font-normal text-white/40 line-through">
                        {p.currency} {p.price}
                      </span>
                      {p.currency} {quote.amount}
                    </>
                  ) : (
                    <>
                      {p.currency} {p.price}
                    </>
                  )}
                </div>
                <button
                  className="grad-bg mt-4 w-full rounded-lg py-2 text-sm font-semibold text-white disabled:opacity-60"
                  onClick={() => buy(p)}
                  disabled={busyPackId !== null || checkout !== null}
                >
                  {busyPackId === p.id ? "Starting…" : "Buy Credits"}
                </button>
              </div>
            );
          })}
          {(!billing || billing.packs.length === 0) && (
            <div className="col-span-3 rounded-xl border border-white/5 p-8 text-center text-sm text-white/50">
              No credit packs available yet.
            </div>
          )}
        </div>
      </div>

      {/* Transaction history */}
      <div className="glass mt-6 rounded-2xl p-6">
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-white">Transaction History</h2>
          <button
            type="button"
            onClick={exportHistory}
            disabled={transactions.length === 0}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-white/80 transition hover:bg-white/10 disabled:opacity-40"
          >
            Export
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-white/50">
                <th className="pb-2">DateTime</th>
                <th className="pb-2">Credits</th>
                <th className="pb-2">Amount</th>
                <th className="pb-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.id} className="border-t border-white/5">
                  <td className="py-2 font-mono text-xs text-white/70">{formatDateTime(t.paid_at || t.created_at)}</td>
                  <td className="py-2 text-white">{t.credit_amount?.toLocaleString() ?? 0}</td>
                  <td className="py-2 text-white/80">
                    {t.currency} {t.amount}
                  </td>
                  <td className="py-2">{statusChip(t.status)}</td>
                </tr>
              ))}
              {transactions.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-white/40">
                    No transactions yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* API endpoint costs */}
      <div className="glass mt-6 rounded-2xl p-6">
        <h2 className="text-sm font-semibold text-white/50">API Endpoints</h2>
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-white/50">
              <th className="pb-2">Endpoint</th>
              <th className="pb-2">Model</th>
              <th className="pb-2">Credits per call</th>
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
                  <Link href="/docs" className="text-xs text-[var(--violet)] hover:underline">
                    View Docs
                  </Link>
                </td>
              </tr>
            ))}
            {pricing.length === 0 && (
              <tr>
                <td colSpan={4} className="py-4 text-center text-white/50">
                  No pricing configured.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="mt-4 text-xs text-white/50">
        Payments are processed securely by ChmabaPay (KHQR / ABA PayWay). Credits are added to your account once payment is confirmed.
      </p>

      {checkout && (
        <KhqrModal
          transactionId={checkout.transaction_id}
          credits={checkout.credits}
          currency={checkout.currency}
          amount={checkout.amount}
          expiresAt={checkout.expires_at}
          onPaid={load}
          onClose={() => setCheckout(null)}
        />
      )}
    </div>
  );
}
