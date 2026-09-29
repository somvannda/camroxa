"use client";

import * as React from "react";
import { Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  createAddonRenewal,
  getAddonRenewal,
  type AddonRenewal,
} from "@/lib/billing";

function formatUsd(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);
}

function formatCredits(value: number | null | undefined) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value ?? 0);
}

/**
 * Renew extra (add-on) channels. Channels never expire and renewal is open at any
 * time; renewing grants credits at the plan rate. The user picks how many 2-channel
 * blocks to renew.
 */
export function AddonRenewalCard() {
  const [data, setData] = React.useState<AddonRenewal | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [buying, setBuying] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [blocks, setBlocks] = React.useState(1);

  React.useEffect(() => {
    let cancelled = false;
    getAddonRenewal()
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setBlocks(result.blocks ?? 1);
        }
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading || !data?.eligible) {
    return null;
  }

  const totalBlocks = data.blocks ?? 1;
  const perBlockCredits = data.credits_per_block ?? 0;
  const perBlockPrice = data.price_per_block_cents ?? 0;
  const options: number[] = [];
  for (let n = 1; n <= totalBlocks; n += 1) options.push(n);

  const priceLabel = formatUsd(perBlockPrice * blocks);
  const creditsLabel = formatCredits(perBlockCredits * blocks);

  async function onRenew() {
    setBuying(true);
    setError(null);
    try {
      const payment = await createAddonRenewal(blocks);
      if (payment.checkout_url) {
        window.location.href = payment.checkout_url;
        return;
      }
      setError("Checkout could not be started. Please try again.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start add-on renewal.");
    } finally {
      setBuying(false);
    }
  }

  return (
    <Card className="rounded-[28px] border-emerald-400/20 bg-[linear-gradient(135deg,rgba(16,52,40,0.30),rgba(10,14,34,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.28)]">
      <CardHeader>
        <CardTitle className="font-display text-2xl text-white">Renew add-on channels</CardTitle>
        <CardDescription className="text-slate-300/80">
          You have {data.addon_channels} extra channels ({totalBlocks} block
          {totalBlocks === 1 ? "" : "s"}). Renewing grants credits at the plan rate
          ({formatCredits(perBlockCredits)} per block). Your channels stay either way.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-[0.18em] text-slate-400">Renew</span>
          {options.map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setBlocks(n)}
              className={
                "h-9 rounded-xl border px-4 text-sm transition " +
                (n === blocks
                  ? "border-emerald-400/40 bg-emerald-500/15 text-white"
                  : "border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]")
              }
            >
              {n * 2} channel{n === 1 ? "" : "s"}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            disabled={buying}
            onClick={() => void onRenew()}
            className="h-11 bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600"
          >
            {buying ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Renew {blocks * 2} channels · {priceLabel} → +{creditsLabel} credits
          </Button>
        </div>
        {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      </CardContent>
    </Card>
  );
}
