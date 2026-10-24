"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import {
  fetchCreditPacks,
  purchaseTopup,
  type CreditPack,
} from "@/lib/pricing-api";

function formatPrice(cents: number): string {
  const amount = Number(cents || 0) / 100;
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: amount % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

export function PricingView() {
  const router = useRouter();
  const { user, credits, loading: authLoading } = useAuth();
  const [packs, setPacks] = useState<CreditPack[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (authLoading) return;
    let active = true;
    setLoading(true);
    setError("");
    fetchCreditPacks()
      .then((nextPacks) => {
        if (active) setPacks(nextPacks);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load credit packs");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading]);

  const startPack = async (pack: CreditPack) => {
    if (!user) {
      router.push("/login?next=/pricing");
      return;
    }
    setBusy(pack.slug);
    setError("");
    try {
      const checkoutUrl = await purchaseTopup(pack.slug);
      window.location.assign(checkoutUrl);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not start checkout");
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow">Credits</div>
            <h1>Top up your credits.</h1>
            <p>Loading credit packs…</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Credits</div>
          <h1>Top up your credits.</h1>
          <p>
            No subscription. Buy a credit pack whenever you need more music.
            Credits are added to your balance and stay there.
          </p>
        </div>
        {user ? (
          <div className="pricing-balance">
            <span>Your balance</span>
            <b>{(credits ?? user.credit_balance ?? 0).toLocaleString()} credits</b>
          </div>
        ) : null}
      </div>

      {error ? (
        <p className="fine" style={{ color: "#f87171", marginBottom: 16 }} role="alert">
          {error}
        </p>
      ) : null}

      <section className="pricing-packs" style={{ marginTop: 0 }}>
        <div className="sec-head">
          <div>
            <h2>Credit packs</h2>
            <p>One-time top-ups. No monthly commitment.</p>
          </div>
        </div>

        {packs.length ? (
          <div className="pack-grid pricing-pack-grid">
            {packs.map((pack) => (
              <article key={pack.id} className="pricing-pack">
                <div className="k">{pack.name}</div>
                <div className="amt">{formatPrice(pack.price_cents)}</div>
                <div className="pricing-pack-credits">
                  <b>{pack.total_credits.toLocaleString()}</b> credits
                  <span>≈ {pack.songs_equivalent.toLocaleString()} songs</span>
                </div>
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={() => startPack(pack)}
                  disabled={busy === pack.slug}
                >
                  {busy === pack.slug
                    ? "Opening checkout…"
                    : user
                      ? "Buy pack"
                      : "Sign in to buy"}
                </button>
              </article>
            ))}
          </div>
        ) : (
          <p className="fine">No credit packs are available right now.</p>
        )}
      </section>

      <p className="pricing-note">
        <Icon name="fa-lock" /> Payments are processed securely by CutLuy.
      </p>
    </div>
  );
}
