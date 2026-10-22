"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface RedeemResult {
  ok: true;
  credits: number;
  code: string;
  balance: number;
}

/**
 * Claim a standalone credit code — the kind created in the admin console as
 * "Redeem for credits". These grant balance credits with no purchase. Discount
 * and bonus codes are applied on the Billing page instead, and the server says
 * so if one is pasted here.
 */
function RedeemInner() {
  const params = useSearchParams();
  // Campaign mail links carry the code in the query string. Seeding the state
  // once from the URL keeps the field editable and avoids an effect round-trip.
  const [code, setCode] = useState(() => (params.get("code") ?? "").trim().toUpperCase());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RedeemResult | null>(null);

  async function redeem(e: React.FormEvent) {
    e.preventDefault();
    const value = code.trim();
    if (!value) return;
    setBusy(true);
    setError("");
    try {
      const res = await apiFetch<RedeemResult>("/me/promo/redeem", {
        method: "POST",
        body: JSON.stringify({ code: value }),
      });
      setResult(res);
      setCode(res.code);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That code could not be redeemed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">Redeem Code</h1>
      <p className="mt-1 text-sm text-white/50">
        Enter a credit code to add credits to your balance.
      </p>

      <div className="glass mt-6 max-w-xl rounded-2xl p-6">
        {result ? (
          <div>
            <div className="flex items-center gap-2 text-[var(--emerald)]">
              <svg
                viewBox="0 0 24 24"
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M20 6L9 17l-5-5" />
              </svg>
              <span className="text-sm font-semibold">Code redeemed</span>
            </div>
            <div className="mt-3 text-4xl font-extrabold text-[var(--emerald)]">
              +{result.credits.toLocaleString()}{" "}
              <span className="text-lg font-semibold text-white/60">credits</span>
            </div>
            <p className="mt-2 text-sm text-white/60">
              Code <span className="font-mono text-white/80">{result.code}</span> added to your
              account.
            </p>
            <p className="mt-1 text-sm text-white/60">
              New balance:{" "}
              <span className="font-semibold text-white">{result.balance.toLocaleString()}</span>{" "}
              credits.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Link
                href="/dashboard/billing"
                className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white"
              >
                Go to Billing
              </Link>
              <button
                type="button"
                onClick={() => {
                  setResult(null);
                  setCode("");
                }}
                className="rounded-lg border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-white/80 transition hover:bg-white/10"
              >
                Redeem another
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={redeem}>
            <label
              htmlFor="redeem-code"
              className="text-xs font-semibold uppercase tracking-wide text-white/50"
            >
              Code
            </label>
            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
              <input
                id="redeem-code"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="CAMX-XXXXXX"
                autoComplete="off"
                spellCheck={false}
                className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-mono text-sm uppercase text-white placeholder:text-white/25 outline-none focus:border-[var(--violet)]/60"
              />
              <button
                type="submit"
                disabled={busy || !code.trim()}
                className="grad-bg inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {busy ? "Redeeming…" : "Redeem"}
              </button>
            </div>
            {error && (
              <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                {error}
              </div>
            )}
            <p className="mt-4 text-xs text-white/35">
              Codes are single use and may expire. Discount and bonus-credit codes are applied on
              the{" "}
              <Link href="/dashboard/billing" className="text-[var(--violet)] hover:underline">
                Billing page
              </Link>{" "}
              when you buy a pack.
            </p>
          </form>
        )}
      </div>
    </div>
  );
}

export default function RedeemPage() {
  return (
    <Suspense fallback={null}>
      <RedeemInner />
    </Suspense>
  );
}
