import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Icon } from "../../components/icon";
import { apiRequest, errorMessage } from "../../lib/api";
import { formatCount } from "../../lib/format";
import { useSessionStore } from "../../store/session";
import { useInAppCheckout, type PaymentStatus } from "../plan/use-in-app-checkout";

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

function formatMoney(cents: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);
}

async function fetchPacks(): Promise<CreditPack[]> {
  const response = await apiRequest<CreditPackList>({
    method: "GET",
    path: "/topups/packs",
    apiVersion: "v3",
  });
  return [...(response?.packs ?? [])].sort((a, b) => a.display_order - b.display_order);
}

/**
 * Login-time credit gate.
 *
 * The account can authenticate (so checkout can be created), but the shell is
 * never shown until paid access is granted. This modal is the only surface.
 */
export function TopUpModal() {
  const applyBootstrap = useSessionStore((state) => state.applyBootstrap);
  const session = useSessionStore((state) => state.session);
  const packsQuery = useQuery<CreditPack[]>({
    queryKey: ["topup-packs"],
    queryFn: fetchPacks,
    retry: 0,
    staleTime: 60_000,
  });

  const [buying, setBuying] = useState("");
  const [checking, setChecking] = useState(false);
  const [notice, setNotice] = useState<{
    tone: "info" | "danger" | "success";
    text: string;
  } | null>(null);
  const [lastCheckout, setLastCheckout] = useState<PurchaseTopup | null>(null);

  const packs = packsQuery.data ?? [];

  const refreshAccess = useCallback(async () => {
    setChecking(true);
    setNotice(null);
    try {
      const restored = await window.camxora.auth.restore();
      if (!restored.ok) {
        setNotice({ tone: "danger", text: restored.error.message });
        return;
      }
      applyBootstrap(restored.data);
      if (restored.data.destination === "topup") {
        setNotice({
          tone: "info",
          text: "No credits detected yet. If you just paid, wait a moment and try again.",
        });
      }
    } catch (cause) {
      setNotice({
        tone: "danger",
        text: cause instanceof Error ? cause.message : "Unable to check access.",
      });
    } finally {
      setChecking(false);
    }
  }, [applyBootstrap]);

  const onPaid = useCallback(
    async (status: PaymentStatus) => {
      setNotice({
        tone: "success",
        text: `${status.credits.toLocaleString()} credits added. Unlocking Desktop Studio…`,
      });
      await refreshAccess();
    },
    [refreshAccess],
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
        await payment.start(purchase.checkout_url, purchase.payment_id, pack.name);
        setNotice({
          tone: "info",
          text: `Complete the payment in the Camxora checkout window for ${pack.name}. Access unlocks automatically.`,
        });
      } catch (cause) {
        setNotice({ tone: "danger", text: errorMessage(cause) || "Unable to start checkout." });
      } finally {
        setBuying("");
      }
    },
    [buying, payment],
  );

  async function signOut() {
    await window.camxora.auth.logout();
    useSessionStore.getState().clear();
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-6">
      <Card className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden p-0">
        <div className="flex items-start justify-between gap-4 border-b border-border p-5">
          <div>
            <p className="text-caption text-text-muted">DESKTOP STUDIO</p>
            <h1 className="mt-0.5 text-title font-semibold text-text-primary">
              Top up credits to continue
            </h1>
            <p className="mt-1 text-meta text-text-secondary">
              {session?.email ?? "Your account"} can sign in, but generation needs a positive credit
              balance.
            </p>
          </div>
          <button
            type="button"
            aria-label="Sign out"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control text-text-muted hover:bg-surface-hover hover:text-text-primary"
            onClick={() => void signOut()}
          >
            <Icon name="fa-xmark" size={14} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {notice ? (
            <div
              className={
                notice.tone === "danger"
                  ? "mb-4 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-meta text-danger"
                  : "mb-4 rounded-control border border-accent-line bg-accent-soft px-3 py-2 text-meta text-text-primary"
              }
              role="status"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>{notice.text}</span>
                {lastCheckout ? (
                  <button
                    type="button"
                    className="text-caption text-accent hover:underline"
                    onClick={() =>
                      void payment.start(
                        lastCheckout.checkout_url,
                        lastCheckout.payment_id,
                        lastCheckout.pack_name,
                      )
                    }
                  >
                    Open checkout
                  </button>
                ) : null}
              </div>
            </div>
          ) : null}

          {packsQuery.isLoading ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {[0, 1, 2, 3].map((index) => (
                <div key={index} className="h-28 animate-pulse rounded-card bg-surface-2" />
              ))}
            </div>
          ) : packsQuery.isError ? (
            <div className="rounded-card border border-danger/30 bg-danger-soft px-4 py-3">
              <p className="text-body text-danger">Credit packs are unavailable right now.</p>
              <p className="mt-1 text-meta text-text-secondary">
                {errorMessage(packsQuery.error)}
              </p>
              <Button className="mt-3" variant="secondary" onClick={() => void packsQuery.refetch()}>
                Retry
              </Button>
            </div>
          ) : packs.length === 0 ? (
            <p className="text-body text-text-secondary">
              No credit packs are published for this account yet.
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {packs.map((pack) => (
                <div
                  key={pack.id}
                  className="flex flex-col rounded-card border border-border bg-surface-1 p-4"
                  data-testid={`topup-pack-${pack.slug}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-body font-semibold text-text-primary">{pack.name}</p>
                    <p className="text-meta text-text-secondary">{formatMoney(pack.price_cents)}</p>
                  </div>
                  <p className="mt-2 text-[24px] font-semibold leading-7 text-text-primary text-tabular">
                    {formatCount(pack.total_credits)}
                    <span className="ml-1 text-meta font-normal text-text-muted">credits</span>
                  </p>
                  <p className="text-caption text-text-muted">
                    ≈ {formatCount(pack.songs_equivalent)} songs
                  </p>
                  <Button
                    variant="primary"
                    className="mt-3 w-full"
                    loading={buying === pack.slug}
                    disabled={Boolean(buying)}
                    onClick={() => void buy(pack)}
                    data-testid={`topup-buy-${pack.slug}`}
                  >
                    Buy {formatMoney(pack.price_cents)}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-4">
          <Button variant="ghost" onClick={() => void signOut()}>
            Use a different account
          </Button>
          <Button variant="secondary" loading={checking} onClick={() => void refreshAccess()}>
            I&apos;ve paid — check access
          </Button>
        </div>
      </Card>
    </div>
  );
}
