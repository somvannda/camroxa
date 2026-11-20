import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "../../components/page-header";
import { Card } from "../../components/card";
import { Button } from "../../components/button";
import { Badge } from "../../components/status";
import { Icon } from "../../components/icon";
import { toast } from "../../components/toast";
import { apiRequest, errorMessage } from "../../lib/api";
import { formatCount, formatCredits, formatDateTime } from "../../lib/format";
import { useAccountOverview } from "../dashboard/use-account-overview";
import { CheckoutDialog } from "./checkout-dialog";
import { useInAppCheckout, type PaymentStatus } from "./use-in-app-checkout";

interface CreditPack {
  id: string;
  slug: string;
  name: string;
  description: string;
  total_credits: number;
  price_cents: number;
  display_order: number;
  songs_equivalent: number;
}

interface CreditPackList {
  packs: CreditPack[];
}

interface PurchaseTopup {
  checkout_url: string;
  payment_id: string;
  pack_name: string;
  credits: number;
  amount_cents: number;
  qr_string?: string;
  expires_at?: string;
}

interface TopupPurchase {
  id: string;
  pack_name: string;
  credits_purchased: number;
  amount_paid_cents: number;
  payment_status: string;
  purchased_at: string;
}

interface TopupHistory {
  purchases: TopupPurchase[];
  total: number;
  limit: number;
  offset: number;
}

interface CreditTransaction {
  id: string;
  amount: number;
  transaction_type: string;
  description: string;
  reference_id: string | null;
  created_at: string;
}

interface CreditHistoryResponse {
  transactions: CreditTransaction[];
  total: number;
  limit: number;
  offset: number;
}

function formatMoney(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

function extraValue(pack: CreditPack, base: CreditPack | undefined): string {
  if (!base || base.price_cents <= 0 || pack.price_cents <= 0) return "Base";
  const baseRate = base.total_credits / base.price_cents;
  const packRate = pack.total_credits / pack.price_cents;
  const percent = Math.round((packRate / baseRate - 1) * 100);
  return percent <= 0 ? "Base" : `+${percent}%`;
}

function creditUnitsToText(units: number): string {
  const credits = Math.abs(units) / 10_000;
  if (credits > 0 && credits < 0.01) return "<0.01";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(credits);
}

function isCodeLabel(value: string): boolean {
  return /^[a-z0-9]+([_.-][a-z0-9]+)+$/i.test(value.trim());
}

function humanizeLedgerType(type: string): string {
  const key = type.trim().toLowerCase().replace(/^v3_/, "").replace(/^consumed_/, "");
  const labels: Record<string, string> = {
    credit_pack_purchase: "Credit pack purchase",
    period_grant_clawback: "Credit grant correction",
    period_grant: "Monthly credit grant",
    music: "Music generation",
    web_music_generation: "Web music generation",
    web_music_lyrics: "Web song lyrics",
    manual_export_stopped: "Manual export stopped",
    video_manual_via_local: "Manual video export",
    "manual export stopped (unused tracks)": "Manual export stopped",
  };
  if (labels[key]) return labels[key];
  const text = key.replace(/[_-]+/g, " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Credit activity";
}

function ledgerLabel(description: string, type: string): string {
  const raw = description.trim();
  if (raw && !isCodeLabel(raw)) return raw;
  return humanizeLedgerType(raw || type);
}

function ledgerIcon(type: string, label: string): string {
  const key = `${type} ${label}`.toLowerCase();
  if (key.includes("music") || key.includes("song") || key.includes("lyric")) return "fa-music";
  if (key.includes("image") || key.includes("thumbnail")) return "fa-image";
  if (key.includes("video") || key.includes("reel") || key.includes("export")) return "fa-video";
  if (key.includes("grant") || key.includes("purchase") || key.includes("credit"))
    return "fa-coins";
  return "fa-bolt";
}

function ledgerTone(type: string): "success" | "neutral" | "warning" {
  const key = type.toLowerCase();
  if (key.includes("consume") || key.includes("music") || key.includes("export")) return "warning";
  if (key.includes("topup") || key.includes("purchase") || key.includes("grant")) return "success";
  return "neutral";
}

async function fetchPacks(): Promise<CreditPack[]> {
  const response = await apiRequest<CreditPackList>({
    method: "GET",
    path: "/topups/packs",
    apiVersion: "v3",
  });
  const packs = Array.isArray(response?.packs) ? response.packs : [];
  return [...packs].sort((a, b) => a.display_order - b.display_order);
}

async function fetchHistory(): Promise<TopupPurchase[]> {
  const response = await apiRequest<TopupHistory>({
    method: "GET",
    path: "/topups/history",
    query: { limit: 12 },
    apiVersion: "v3",
  });
  return Array.isArray(response?.purchases) ? response.purchases : [];
}

async function fetchLedger(): Promise<CreditTransaction[]> {
  const response = await apiRequest<CreditHistoryResponse>({
    method: "GET",
    path: "/credits/history",
    query: { limit: 25 },
    apiVersion: "v3",
  });
  return Array.isArray(response?.transactions) ? response.transactions : [];
}

export function PlanPage() {
  const account = useAccountOverview();
  const packsQuery = useQuery<CreditPack[]>({
    queryKey: ["topup-packs"],
    queryFn: fetchPacks,
    retry: 0,
    staleTime: 60_000,
  });
  const historyQuery = useQuery<TopupPurchase[]>({
    queryKey: ["topup-history"],
    queryFn: fetchHistory,
    retry: 0,
    staleTime: 0,
  });
  const ledgerQuery = useQuery<CreditTransaction[]>({
    queryKey: ["credit-ledger"],
    queryFn: fetchLedger,
    retry: 0,
    staleTime: 0,
  });

  const [buying, setBuying] = useState("");
  const [notice, setNotice] = useState<{ tone: "success" | "danger" | "info"; text: string } | null>(
    null,
  );
  const [lastCheckout, setLastCheckout] = useState<PurchaseTopup | null>(null);

  const packs = packsQuery.data ?? [];
  const ledgerRows = (ledgerQuery.data ?? []).filter((entry) => entry.amount > 0);
  const balance = account.data?.me.credit_balance ?? 0;
  const loadingAccount = account.isLoading && !account.data;

  const refresh = useCallback(async () => {
    await Promise.allSettled([
      account.refetch(),
      historyQuery.refetch(),
      ledgerQuery.refetch(),
      packsQuery.refetch(),
    ]);
  }, [account, historyQuery, ledgerQuery, packsQuery]);

  const onPaid = useCallback(
    async (status: PaymentStatus) => {
      setNotice({
        tone: "success",
        text: `${formatCredits(status.credits)} credits were added to your balance.`,
      });
      toast(`${formatCredits(status.credits)} credits added.`, "success");
      await refresh();
    },
    [refresh],
  );
  const payment = useInAppCheckout(onPaid);

  const buy = useCallback(
    async (pack: CreditPack) => {
      if (buying) return;
      setBuying(pack.slug);
      setNotice(null);
      try {
        const purchase = await apiRequest<PurchaseTopup>({
          method: "POST",
          path: "/topups/purchase",
          body: { pack_slug: pack.slug },
          apiVersion: "v3",
        });
        if (!purchase.checkout_url) {
          setNotice({ tone: "danger", text: "The checkout link is missing. Try again." });
          return;
        }
        setLastCheckout(purchase);
        payment.start({
          paymentId: purchase.payment_id,
          checkoutUrl: purchase.checkout_url,
          packName: pack.name,
          qrString: purchase.qr_string ?? "",
          amountCents: purchase.amount_cents,
          expiresAt: purchase.expires_at ?? "",
        });
        setNotice({
          tone: "info",
          text: `Complete the payment in the Camxora checkout window for ${pack.name}. Credits appear here automatically.`,
        });
      } catch (cause) {
        setNotice({ tone: "danger", text: errorMessage(cause) || "Unable to start checkout." });
      } finally {
        setBuying("");
      }
    },
    [buying, payment],
  );

  return (
    <div className="pb-6" data-testid="plan-page">
      <PageHeader
        eyebrow="Credits"
        title="Buy credits."
        description="One-time purchase. No subscription. Start free, or add a pack whenever you need more."
      />

      <div className="space-y-4 p-5">
        <div className="grid gap-4 xl:grid-cols-[1.15fr_1fr]">
          <Card className="flex items-center justify-between gap-4 p-4" data-testid="plan-balance">
            <div>
              <p className="text-caption text-text-muted">Available credits</p>
              <p className="mt-1 text-[32px] font-semibold leading-9 text-text-primary text-tabular">
                {loadingAccount ? "--" : formatCredits(balance)}
              </p>
              <p className="text-meta text-text-secondary">
                Every generation is paid from this balance. No plans or quotas.
              </p>
            </div>
            <Button variant="secondary" onClick={() => void refresh()} disabled={account.isFetching}>
              <Icon name="fa-arrows-rotate" size={13} />
              Refresh
            </Button>
          </Card>

          <Card className="p-4" data-testid="plan-recent">
            <div className="flex items-baseline justify-between gap-2">
              <h2 className="text-title font-semibold text-text-primary">Recent top-ups</h2>
              <Badge tone="neutral">{formatCount(historyQuery.data?.length ?? 0)}</Badge>
            </div>
            <div className="mt-2 max-h-32 overflow-auto">
              {historyQuery.isLoading ? (
                <p className="text-meta text-text-secondary">Loading purchases…</p>
              ) : historyQuery.isError ? (
                <p className="text-meta text-text-secondary">Purchase history is unavailable.</p>
              ) : (historyQuery.data?.length ?? 0) === 0 ? (
                <p className="text-meta text-text-secondary">No top-ups yet.</p>
              ) : (
                <ul className="divide-y divide-border">
                  {historyQuery.data?.map((purchase) => (
                    <li key={purchase.id} className="flex items-center justify-between gap-2 py-1.5">
                      <div className="min-w-0">
                        <p className="truncate text-meta text-text-primary">{purchase.pack_name}</p>
                        <p className="text-caption text-text-muted">
                          {formatDateTime(purchase.purchased_at)}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-meta text-text-primary text-tabular">
                          +{formatCredits(purchase.credits_purchased)}
                        </p>
                        <p className="text-caption text-text-muted">
                          {formatMoney(purchase.amount_paid_cents)}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>
        </div>

        {notice ? (
          <Card
            className={
              notice.tone === "danger"
                ? "border-danger/30 bg-danger-soft px-4 py-2 text-body text-danger"
                : notice.tone === "success"
                  ? "border-success/30 bg-success-soft px-4 py-2 text-body text-success"
                  : "border-accent-line bg-accent-soft px-4 py-2 text-body text-text-primary"
            }
            role="status"
          >
            <div className="flex items-center justify-between gap-3">
              <span>{notice.text}</span>
              {lastCheckout?.checkout_url ? (
                <Button
                  variant="ghost"
                  className="h-7 shrink-0 px-2 text-caption"
                  onClick={() =>
                    payment.start({
                      paymentId: lastCheckout.payment_id,
                      checkoutUrl: lastCheckout.checkout_url,
                      packName: lastCheckout.pack_name,
                      qrString: lastCheckout.qr_string ?? "",
                      amountCents: lastCheckout.amount_cents,
                      expiresAt: lastCheckout.expires_at ?? "",
                    })
                  }
                >
                  Open checkout
                </Button>
              ) : null}
            </div>
          </Card>
        ) : null}

        <div>
          <h2 className="text-title font-semibold text-text-primary">Credit packs</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            Every paid pack is a one-time purchase. Credits are valid for 30 days from purchase.
          </p>
        </div>

        {packsQuery.isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((index) => (
              <Card key={index} className="h-44 animate-pulse bg-surface-2" />
            ))}
          </div>
        ) : packsQuery.isError ? (
          <Card className="p-4" role="alert">
            <p className="text-body text-text-primary">Credit packs are unavailable right now.</p>
            <p className="mt-1 text-meta text-text-secondary">{errorMessage(packsQuery.error)}</p>
            <Button className="mt-3" variant="secondary" onClick={() => void packsQuery.refetch()}>
              Retry
            </Button>
          </Card>
        ) : packs.length === 0 ? (
          <Card className="p-4">
            <p className="text-body text-text-secondary">
              No credit packs are published for this account yet.
            </p>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {packs.map((pack, index) => {
              const popular =
                pack.slug === "medium" ||
                /medium/i.test(pack.name) ||
                (packs.length > 1 && index === 0 && packs.length === 1);
              const extra = extraValue(pack, packs[0]);
              return (
                <Card
                  key={pack.id}
                  className={
                    popular
                      ? "relative flex flex-col border-accent-line p-4"
                      : "flex flex-col p-4"
                  }
                  data-testid={`plan-pack-${pack.slug}`}
                >
                  {popular ? (
                    <span className="absolute right-3 top-3">
                      <Badge tone="accent">Most popular</Badge>
                    </span>
                  ) : null}
                  <div className="flex items-center gap-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-control bg-accent-soft text-accent">
                      <Icon name={popular ? "fa-crown" : "fa-bolt"} size={12} />
                    </span>
                    <p className="text-body font-semibold text-text-primary">{pack.name}</p>
                  </div>

                  <div className="mt-3 flex items-end justify-between gap-3">
                    <div>
                      <p className="text-[26px] font-semibold leading-8 text-text-primary text-tabular">
                        {formatCredits(pack.total_credits)}
                      </p>
                      <p className="text-[10px] uppercase tracking-wide text-text-muted">Credits</p>
                    </div>
                    <div className="text-right">
                      <p className="text-[20px] font-semibold leading-7 text-text-primary text-tabular">
                        {formatMoney(pack.price_cents)}
                      </p>
                      <p className="text-[10px] uppercase tracking-wide text-text-muted">
                        One-time
                      </p>
                    </div>
                  </div>

                  <dl className="mt-3 divide-y divide-border border-t border-border text-caption">
                    <div className="flex items-center justify-between gap-2 py-1.5">
                      <dt className="text-text-muted">Total songs</dt>
                      <dd className="text-text-secondary text-tabular">
                        {formatCount(pack.songs_equivalent)}
                      </dd>
                    </div>
                    <div className="flex items-center justify-between gap-2 py-1.5">
                      <dt className="text-text-muted">Extra value</dt>
                      <dd
                        className={
                          extra === "Base"
                            ? "text-text-secondary text-tabular"
                            : "text-success text-tabular"
                        }
                      >
                        {extra}
                      </dd>
                    </div>
                    <div className="flex items-center justify-between gap-2 py-1.5">
                      <dt className="text-text-muted">Valid</dt>
                      <dd className="text-text-secondary">30 days</dd>
                    </div>
                    <div className="flex items-center justify-between gap-2 py-1.5">
                      <dt className="text-text-muted">Delivery</dt>
                      <dd className="text-success">Instant</dd>
                    </div>
                  </dl>

                  <Button
                    variant={popular ? "primary" : "secondary"}
                    className="mt-4 w-full"
                    loading={buying === pack.slug}
                    disabled={Boolean(buying)}
                    onClick={() => void buy(pack)}
                    data-testid={`plan-buy-${pack.slug}`}
                  >
                    {buying === pack.slug ? "Opening checkout…" : `Buy ${pack.name}`}
                  </Button>
                </Card>
              );
            })}
          </div>
        )}

        <Card className="overflow-hidden" data-testid="plan-billing">
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
            <div>
              <h2 className="text-title font-semibold text-text-primary">Billing activity</h2>
              <p className="mt-0.5 text-meta text-text-secondary">
                Purchases, grants and credit usage from the wallet ledger.
              </p>
            </div>
            <Button
              variant="ghost"
              className="h-7 px-2 text-caption"
              onClick={() => void ledgerQuery.refetch()}
              disabled={ledgerQuery.isFetching}
            >
              Refresh
            </Button>
          </div>

          {ledgerQuery.isLoading ? (
            <div className="space-y-2 p-4" aria-hidden="true">
              {[0, 1, 2, 3].map((index) => (
                <div key={index} className="h-9 rounded-control bg-surface-2" />
              ))}
            </div>
          ) : ledgerQuery.isError ? (
            <div className="px-4 py-6 text-center">
              <p className="text-meta text-text-secondary">Billing activity is unavailable.</p>
              <Button className="mt-2" variant="secondary" onClick={() => void ledgerQuery.refetch()}>
                Retry
              </Button>
            </div>
          ) : ledgerRows.length === 0 ? (
            <p className="px-4 py-6 text-center text-meta text-text-secondary">
              No credit activity yet. Purchases and generation costs appear here.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {ledgerRows.map((entry) => {
                const consumed = entry.transaction_type.toLowerCase() === "consume";
                const label = ledgerLabel(entry.description, entry.transaction_type);
                return (
                  <li
                    key={entry.id}
                    className="flex items-center gap-3 px-4 py-2.5"
                  >
                    <span
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control bg-surface-2 text-text-secondary"
                      aria-hidden="true"
                    >
                      <Icon name={ledgerIcon(entry.transaction_type, label)} size={12} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-meta font-medium text-text-primary">{label}</p>
                      <p className="text-caption text-text-muted">
                        {formatDateTime(entry.created_at)}
                      </p>
                    </div>
                    <Badge tone={ledgerTone(entry.transaction_type)}>
                      {consumed ? "Used" : "Added"}
                    </Badge>
                    <span
                      className={
                        consumed
                          ? "w-28 text-right text-meta text-warning text-tabular"
                          : "w-28 text-right text-meta text-success text-tabular"
                      }
                    >
                      {consumed ? "−" : "+"}
                      {creditUnitsToText(entry.amount)}
                      <span className="ml-1 text-caption">credits</span>
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card className="p-4" data-testid="plan-includes">
          <div className="flex items-center gap-2 text-body font-medium text-text-primary">
            <Icon name="fa-wand-magic-sparkles" size={13} className="text-accent" />
            Every pack includes
          </div>
          <div className="mt-3 grid gap-2 text-meta text-text-secondary sm:grid-cols-2 xl:grid-cols-3">
            {[
              "Credits added instantly after payment",
              "Valid for 30 days from purchase",
              "Buying again resets the 30-day clock",
              "No subscription required",
              "Buy another pack any time",
              "Secure ChmabaPay checkout",
            ].map((item) => (
              <span key={item} className="flex items-start gap-2">
                <Icon name="fa-check" size={11} className="mt-1 shrink-0 text-success" />
                {item}
              </span>
            ))}
          </div>
          <p className="mt-3 flex items-center gap-2 border-t border-border pt-3 text-caption text-text-muted">
            <Icon name="fa-lock" size={11} />
            Payments are processed securely by ChmabaPay.
          </p>
        </Card>
      </div>

      <CheckoutDialog
        session={payment.pending}
        credits={lastCheckout?.credits ?? 0}
        onClose={() => {
          payment.close();
          setNotice(null);
        }}
      />
    </div>
  );
}
