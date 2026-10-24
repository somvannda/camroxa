"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import {
  fetchCreditPacks,
  fetchFreePlan,
  purchaseTopup,
  type CreditPack,
  type FreePlan,
} from "@/lib/pricing-api";

function formatPrice(cents: number, decimals = false): string {
  const amount = Number(cents || 0) / 100;
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals || amount % 1 !== 0 ? 2 : 0,
    maximumFractionDigits: 2,
  });
}

function currentPlanBase(name?: string | null): string {
  return (name || "free")
    .toLowerCase()
    .replace(/[_-](monthly|yearly)$/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function extraValue(pack: CreditPack, base?: CreditPack): string {
  if (!base || base.price_cents <= 0 || pack.price_cents <= 0) return "Base";
  const baseRate = base.total_credits / base.price_cents;
  const packRate = pack.total_credits / pack.price_cents;
  const pct = Math.round((packRate / baseRate - 1) * 100);
  return pct <= 0 ? "Base" : `+${pct}%`;
}

export function PricingView() {
  const router = useRouter();
  const { user, credits, loading: authLoading } = useAuth();
  const [packs, setPacks] = useState<CreditPack[]>([]);
  const [freePlan, setFreePlan] = useState<FreePlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (authLoading) return;
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([fetchCreditPacks(), fetchFreePlan().catch(() => null)])
      .then(([nextPacks, nextFree]) => {
        if (!active) return;
        setPacks(nextPacks);
        setFreePlan(nextFree);
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

  const startFree = () => {
    router.push(user ? "/create" : "/signup");
  };

  const basePack = packs[0];
  const freeIsCurrent = Boolean(user) && currentPlanBase(user?.plan_name) === "free";
  const freeSongs = freePlan
    ? Math.floor(freePlan.monthly_credits / Number(freePlan.credits_per_generate || 10)) * 2
    : 0;

  if (loading) {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow">Credits</div>
            <h1>Buy credits.</h1>
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
          <h1>Buy credits.</h1>
          <p>
            One-time purchase. No subscription. Start free, or add a pack
            whenever you need more music.
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
            <p>Every paid pack is a one-time purchase. Credits are valid for 30 days.</p>
          </div>
        </div>

        <div className="pricing-pack-grid">
          {freePlan ? (
            <article className="pricing-pack free">
              <div className="pack-title">
                <span className="pack-icon">
                  <Icon name="fa-gift" />
                </span>
                <b>Free</b>
              </div>
              <div className="pack-head">
                <div className="pack-stat">
                  <b>{freePlan.monthly_credits.toLocaleString()}</b>
                  <span>CREDITS</span>
                </div>
                <div className="pack-stat right">
                  <b>$0</b>
                  <span>FREE</span>
                </div>
              </div>
              <div className="pack-rows">
                <div className="pack-row">
                  <span>Total songs</span>
                  <b>{freeSongs.toLocaleString()}</b>
                </div>
                <div className="pack-row">
                  <span>Extra value</span>
                  <b>Starter</b>
                </div>
                <div className="pack-row">
                  <span>Valid</span>
                  <b>Monthly</b>
                </div>
                <div className="pack-row">
                  <span>Delivery</span>
                  <b className="instant">Instant</b>
                </div>
              </div>
              <button
                className="btn btn-ghost pack-buy"
                type="button"
                onClick={startFree}
                disabled={freeIsCurrent}
              >
                {freeIsCurrent ? "Current plan" : user ? "Start creating" : "Start free"}
              </button>
            </article>
          ) : null}

          {packs.map((pack) => {
            const popular = pack.slug === "medium" || /medium/i.test(pack.name);
            return (
              <article key={pack.id} className={`pricing-pack${popular ? " popular" : ""}`}>
                {popular ? <span className="pricing-badge">Most popular</span> : null}
                <div className="pack-title">
                  <span className="pack-icon">
                    <Icon name={popular ? "fa-crown" : "fa-bolt"} />
                  </span>
                  <b>{pack.name}</b>
                </div>
                <div className="pack-head">
                  <div className="pack-stat">
                    <b>{pack.total_credits.toLocaleString()}</b>
                    <span>CREDITS</span>
                  </div>
                  <div className="pack-stat right">
                    <b>{formatPrice(pack.price_cents, true)}</b>
                    <span>ONE-TIME</span>
                  </div>
                </div>
                <div className="pack-rows">
                  <div className="pack-row">
                    <span>Total songs</span>
                    <b>{pack.songs_equivalent.toLocaleString()}</b>
                  </div>
                  <div className="pack-row">
                    <span>Extra value</span>
                    <b className={extraValue(pack, basePack) !== "Base" ? "extra" : ""}>
                      {extraValue(pack, basePack)}
                    </b>
                  </div>
                  <div className="pack-row">
                    <span>Valid</span>
                    <b>30 days</b>
                  </div>
                  <div className="pack-row">
                    <span>Delivery</span>
                    <b className="instant">Instant</b>
                  </div>
                </div>
                <button
                  className={`btn ${popular ? "btn-primary" : "btn-ghost"} pack-buy`}
                  type="button"
                  onClick={() => startPack(pack)}
                  disabled={busy === pack.slug}
                >
                  {busy === pack.slug ? "Opening checkout…" : `Buy ${pack.name}`}
                </button>
              </article>
            );
          })}
        </div>
      </section>

      <section className="pricing-includes">
        <div className="pricing-includes-title">
          <Icon name="fa-wand-magic-sparkles" /> Every pack includes
        </div>
        <div className="pricing-includes-grid">
          <span><Icon name="fa-check" /> Credits added instantly after payment</span>
          <span><Icon name="fa-check" /> Valid for 30 days from purchase</span>
          <span><Icon name="fa-check" /> Buying again resets the 30-day clock</span>
          <span><Icon name="fa-check" /> No subscription required</span>
          <span><Icon name="fa-check" /> Buy another pack any time</span>
          <span><Icon name="fa-check" /> Secure ChmabaPay checkout</span>
        </div>
      </section>

      <p className="pricing-note">
        <Icon name="fa-lock" />
        <span>
          Payments are processed securely by{" "}
          <a href="https://pay.chmaba.com/" target="_blank" rel="noreferrer">
            ChmabaPay
          </a>
          .
        </span>
      </p>
    </div>
  );
}
