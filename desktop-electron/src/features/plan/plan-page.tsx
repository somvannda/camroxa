import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "../../components/page-header";
import { Card } from "../../components/card";
import { Button } from "../../components/button";
import { Badge } from "../../components/status";
import { Icon } from "../../components/icon";
import { toast } from "../../components/toast";
import { apiRequest, errorMessage } from "../../lib/api";
import { formatCount, formatDateTime } from "../../lib/format";
import { useAccountOverview } from "../dashboard/use-account-overview";

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

function pricePer100(pack: CreditPack): string {
  if (pack.total_credits <= 0) return "--";
  return formatMoney(Math.round((pack.price_cents / pack.total_credits) * 100));
}

function savingsPercent(pack: CreditPack, packs: CreditPack[]): number {
  if (packs.length === 0 || pack.total_credits <= 0) return 0;
  const baseline = packs.reduce((worst, entry) =>
    entry.price_cents / Math.max(1, entry.total_credits) >
    worst.price_cents / Math.max(1, worst.total_credits)
      ? entry
      : worst,
  );
  const baselineRate = baseline.price_cents / Math.max(1, baseline.total_credits);
  const rate = pack.price_cents / Math.max(1, pack.total_credits);
  if (baselineRate <= 0) return 0;
  return Math.max(0, Math.round((1 - rate / baselineRate) * 100));
}

function ledgerTone(type: string): "success" | "neutral" | "warning" {
  const key = type.toLowerCase();
  if (key === "consume") return "warning";
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
  const [checkout, setCheckout] = useState<PurchaseTopup | null>(null);

  const packs = packsQuery.data ?? [];
  const balance = account.data?.me.credit_balance ?? 0;
  const loadingAccount = account.isLoading && !account.data;

  const bestValue = useMemo(() => {
    const list = packsQuery.data ?? [];
    if (list.length === 0) return null;
    return list.reduce((best, pack) =>
      pack.total_credits / Math.max(1, pack.price_cents) >
      best.total_credits / Math.max(1, best.price_cents)
        ? pack
        : best,
    ).slug;
  }, [packsQuery.data]);

  const refresh = useCallback(async () => {
    await Promise.allSettled([
      account.refetch(),
      historyQuery.refetch(),
      ledgerQuery.refetch(),
      packsQuery.refetch(),
    ]);
  }, [account, historyQuery, ledgerQuery, packsQuery]);

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
        setCheckout(purchase);
        const opened = await window.camxora.app.openExternal(purchase.checkout_url);
        if (!opened.ok) {
          setNotice({ tone: "danger", text: opened.error.message });
          return;
        }
        setNotice({
          tone: "info",
          text: `Checkout opened in your browser for ${pack.name}. Finish the payment, then refresh the balance.`,
        });
        toast("Checkout opened in your browser.", "info", 6000);
      } catch (cause) {
        setNotice({ tone: "danger", text: errorMessage(cause) || "Unable to start checkout." });
      } finally {
        setBuying("");
      }
    },
    [buying],
  );

  return (
    <div className="pb-6" data-testid="plan-page">
      <PageHeader
        eyebrow="Account"
        title="Plan"
        description="Top up the credit balance used by music, images, video and uploads."
      />

      <div className="space-y-4 p-5">
        <div className="grid gap-4 xl:grid-cols-[1.15fr_1fr]">
          <Card className="flex items-center justify-between gap-4 p-4" data-testid="plan-balance">
            <div>
              <p className="text-caption text-text-muted">Available credits</p>
              <p className="mt-1 text-[32px] font-semibold leading-9 text-text-primary text-tabular">
                {loadingAccount ? "--" : formatCount(balance)}
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
                          +{formatCount(purchase.credits_purchased)}
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
              {checkout?.checkout_url ? (
                <Button
                  variant="ghost"
                  className="h-7 shrink-0 px-2 text-caption"
                  onClick={() => void window.camxora.app.openExternal(checkout.checkout_url)}
                >
                  Reopen checkout
                </Button>
              ) : null}
            </div>
          </Card>
        ) : null}

        <div>
          <h2 className="text-title font-semibold text-text-primary">Credit packs</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            One purchase adds credits to this account immediately after payment.
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
            {packs.map((pack) => {
              const saving = savingsPercent(pack, packs);
              return (
                <Card
                  key={pack.id}
                  className={
                    pack.slug === bestValue
                      ? "flex flex-col border-accent-line p-4"
                      : "flex flex-col p-4"
                  }
                  data-testid={`plan-pack-${pack.slug}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-body font-semibold text-text-primary">{pack.name}</h3>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      {pack.slug === bestValue ? <Badge tone="accent">Best value</Badge> : null}
                      {saving > 0 ? <Badge tone="success">Save {saving}%</Badge> : null}
                    </div>
                  </div>
                  <p className="mt-2 text-[26px] font-semibold leading-8 text-text-primary text-tabular">
                    {formatCount(pack.total_credits)}
                    <span className="ml-1 text-meta font-normal text-text-muted">credits</span>
                  </p>
                  <p className="text-body font-medium text-text-primary">
                    {formatMoney(pack.price_cents)}
                    <span className="ml-1 text-caption font-normal text-text-muted">
                      one-time
                    </span>
                  </p>
                  <dl className="mt-3 space-y-1 border-t border-border pt-3 text-caption">
                    <div className="flex items-baseline justify-between gap-2">
                      <dt className="text-text-muted">Songs equivalent</dt>
                      <dd className="text-text-secondary text-tabular">
                        ≈ {formatCount(pack.songs_equivalent)}
                      </dd>
                    </div>
                    <div className="flex items-baseline justify-between gap-2">
                      <dt className="text-text-muted">Per 100 credits</dt>
                      <dd className="text-text-secondary text-tabular">{pricePer100(pack)}</dd>
                    </div>
                    <div className="flex items-baseline justify-between gap-2">
                      <dt className="text-text-muted">Validity</dt>
                      <dd className="text-text-secondary">Added after payment</dd>
                    </div>
                  </dl>
                  {pack.description ? (
                    <p className="mt-2 text-caption text-text-muted">{pack.description}</p>
                  ) : null}
                  <ul className="mt-2 space-y-1 text-caption text-text-secondary">
                    <li>Music, image, video, merge and upload operations</li>
                    <li>No subscription; buy again whenever you need more</li>
                  </ul>
                  <Button
                    variant="primary"
                    className="mt-4 w-full"
                    loading={buying === pack.slug}
                    disabled={Boolean(buying)}
                    onClick={() => void buy(pack)}
                    data-testid={`plan-buy-${pack.slug}`}
                  >
                    Buy {formatMoney(pack.price_cents)}
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
          ) : (ledgerQuery.data?.length ?? 0) === 0 ? (
            <p className="px-4 py-6 text-center text-meta text-text-secondary">
              No credit activity yet. Purchases and generation costs appear here.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {ledgerQuery.data?.map((entry) => {
                const consumed = entry.transaction_type.toLowerCase() === "consume";
                const label =
                  entry.description ||
                  (consumed ? "Generation" : entry.transaction_type.replace(/[_-]+/g, " "));
                return (
                  <li
                    key={entry.id}
                    className="flex items-center justify-between gap-3 px-4 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-meta text-text-primary capitalize">{label}</p>
                      <p className="text-caption text-text-muted">
                        {formatDateTime(entry.created_at)}
                        {entry.reference_id ? ` · ${entry.reference_id.slice(0, 8)}` : ""}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <Badge tone={ledgerTone(entry.transaction_type)}>
                        {consumed ? "Used" : "Added"}
                      </Badge>
                      <span
                        className={
                          consumed
                            ? "text-meta text-warning text-tabular"
                            : "text-meta text-success text-tabular"
                        }
                      >
                        {consumed ? "−" : "+"}
                        {formatCount(entry.amount)}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card className="p-4">
          <h2 className="text-title font-semibold text-text-primary">How credits work</h2>
          <ul className="mt-2 space-y-1 text-meta text-text-secondary">
            <li>Music, drafts, images, video renders, merges and uploads are priced per operation.</li>
            <li>The exact cost is shown on the Music page before you generate.</li>
            <li>Unused credits stay on your account; there is no monthly allowance to lose.</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
