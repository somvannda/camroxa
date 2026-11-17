"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import { Icon } from "@/components/Icon";
import { Switch } from "@/components/ui/switch";
import { fetchCreditPacks, purchaseTopup, type CreditPack } from "@/lib/pricing-api";

/**
 * S61 — the captured "You're out of credits" modal (`docs/studio/reference/screens/
 * S61-insufficient-credits.jpeg`).
 *
 * The frame: a 480px dark card with a title, a "Monthly credits used / 100%" meter,
 * body copy, an amount stepper ($6 in the capture), a "Turn on auto-reload" control,
 * a white purchase pill and "Not now".
 *
 * Two things are data-bound on purpose:
 *   - the amount comes from the pricing API (`/topups/packs/public`). CAMXORA's ladder
 *     is $5 / $10 / $30, so the stepper shows those prices, never a hard-coded $6.
 *   - auto-reload has no server capability (there is no recurring top-up endpoint and
 *     `POST /topups/purchase` sells one pack per checkout), so the switch renders
 *     disabled with an explanation instead of pretending to persist a subscription.
 *     The preference helpers still round-trip in the session for when it can be wired.
 */

export const AUTO_RELOAD_STORAGE_KEY = "camxora:credits-auto-reload";
/** No recurring top-up endpoint exists yet, so the switch cannot be turned on. */
export const AUTO_RELOAD_SUPPORTED = false;

/** `$5`, `$10`, `$10.50` — matches the capture's `$6` shape (no cents when whole). */
export function formatPackPrice(cents: number): string {
  const value = Math.max(0, Math.round(Number(cents) || 0)) / 100;
  const whole = Math.floor(value);
  const fraction = Math.round((value - whole) * 100);
  return fraction === 0 ? `$${whole}` : `$${whole}.${String(fraction).padStart(2, "0")}`;
}

/**
 * Share of the grant already spent, for the meter under the title.
 *
 * The modal only opens after a charge was refused, so an unknown allowance still
 * reads 100% — the spendable balance is gone. Known numbers are clamped.
 */
export function creditsUsedPercent(
  remaining: number | null | undefined,
  allowance: number | null | undefined
): number {
  const total = Number(allowance ?? 0);
  const left = Number(remaining ?? 0);
  if (!Number.isFinite(total) || total <= 0) return 100;
  if (!Number.isFinite(left) || left <= 0) return 100;
  const used = Math.round(((total - left) / total) * 100);
  return Math.min(100, Math.max(0, used));
}

/** Step target, clamped to the ladder the API returned. */
export function packAt(packs: CreditPack[], index: number): CreditPack | null {
  if (!packs.length) return null;
  const safe = Math.min(Math.max(Math.trunc(index) || 0, 0), packs.length - 1);
  return packs[safe] ?? null;
}

/** Session-scoped auto-reload preference (survives reloads, not the tab's life). */
export function readAutoReloadPreference(
  storage: Pick<Storage, "getItem"> | null | undefined
): boolean {
  try {
    return storage?.getItem(AUTO_RELOAD_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function writeAutoReloadPreference(
  storage: Pick<Storage, "setItem"> | null | undefined,
  enabled: boolean
): void {
  try {
    storage?.setItem(AUTO_RELOAD_STORAGE_KEY, enabled ? "1" : "0");
  } catch {
    /* private mode / quota — the preference is best effort */
  }
}

type CreateCreditsModalProps = {
  open: boolean;
  /** Credits still spendable, for the usage meter. */
  creditsRemaining?: number | null;
  /** Monthly grant the meter is measured against (`creditAllowance` from auth). */
  monthlyAllowance?: number | null;
  onClose: () => void;
  /** Called after checkout was created, so the caller can refresh balances. */
  onCheckoutStarted?: () => void;
};

export function CreateCreditsModal({
  open,
  creditsRemaining = null,
  monthlyAllowance = null,
  onClose,
  onCheckoutStarted,
}: CreateCreditsModalProps) {
  const [packs, setPacks] = useState<CreditPack[] | null>(null);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [checkoutError, setCheckoutError] = useState("");
  const [busy, setBusy] = useState(false);
  const [autoReload, setAutoReload] = useState(false);
  const titleRef = useRef<HTMLHeadingElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const titleId = useId();
  const switchLabelId = useId();
  const switchNoteId = useId();

  const usagePercent = creditsUsedPercent(creditsRemaining, monthlyAllowance);
  const pack = packAt(packs ?? [], step);

  // Prices are public and change in the admin console; re-read them every open.
  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    setLoadError("");
    setCheckoutError("");
    setStep(0);
    fetchCreditPacks()
      .then((next) => {
        if (active) setPacks(next);
      })
      .catch((cause) => {
        if (active) {
          setPacks([]);
          setLoadError(
            cause instanceof Error ? cause.message : "Could not load credit packs."
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [open]);

  // The preference is session-scoped; read it back so a reload keeps the choice.
  useEffect(() => {
    if (!open || typeof window === "undefined") return;
    setAutoReload(readAutoReloadPreference(window.sessionStorage));
  }, [open]);

  // The parent passes an inline handler; keep it out of the focus/scroll effect so a
  // parent re-render never re-focuses the title or re-adds the listener.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  // Focus the title (labelled control), lock scroll and close on Escape.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    titleRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRef.current();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open]);

  const toggleAutoReload = useCallback((next: boolean) => {
    setAutoReload(next);
    if (typeof window !== "undefined") {
      writeAutoReloadPreference(window.sessionStorage, next);
    }
  }, []);

  const startCheckout = useCallback(async () => {
    if (!pack || busy) return;
    setBusy(true);
    setCheckoutError("");
    try {
      const checkout = await purchaseTopup(pack.slug);
      if (typeof window !== "undefined") {
        window.sessionStorage.setItem("camxora:checkout-payment", checkout.paymentId);
      }
      onCheckoutStarted?.();
      window.location.assign(checkout.checkoutUrl);
    } catch (cause) {
      setCheckoutError(
        cause instanceof Error ? cause.message : "Could not start checkout."
      );
      setBusy(false);
    }
  }, [busy, onCheckoutStarted, pack]);

  // Keep Tab inside the dialog while it owns the screen.
  const onDialogKeyDown = useCallback((event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Tab") return;
    const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusables?.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }, []);

  if (!open) return null;

  return (
    <div className="s-modal-overlay" onClick={onClose}>
      <div
        ref={dialogRef}
        className="s-credits-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={onDialogKeyDown}
      >
        <button type="button" className="s-credits-close" aria-label="Close" onClick={onClose}>
          <Icon name="fa-xmark" />
        </button>

        <h2 id={titleId} ref={titleRef} tabIndex={-1} className="s-credits-title">
          You&apos;re out of credits
        </h2>

        <div className="s-credits-meter">
          <div className="s-credits-meter-row">
            <span>Monthly credits used</span>
            <b>{usagePercent}%</b>
          </div>
          <div
            className="s-credits-meter-track"
            role="progressbar"
            aria-label="Monthly credits used"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={usagePercent}
          >
            <span style={{ width: `${usagePercent}%` }} />
          </div>
        </div>

        <p className="s-credits-body">
          Get back to creating. Top up right away and keep generating — credit packs are a
          one-time purchase, and your credits stay valid for 30 days.
        </p>

        {loading ? (
          <p className="s-note s-credits-loading">Loading credit packs…</p>
        ) : pack ? (
          <>
            <p className="s-credits-caption">Auto-reload amount</p>
            <div className="s-credits-stepper">
              <button
                type="button"
                className="s-credits-step"
                aria-label="Decrease amount"
                disabled={step <= 0 || busy}
                onClick={() => setStep((current) => Math.max(0, current - 1))}
              >
                <Icon name="fa-minus" />
              </button>
              <span className="s-credits-amount" data-testid="credits-modal-amount">
                {formatPackPrice(pack.price_cents)}
              </span>
              <button
                type="button"
                className="s-credits-step"
                aria-label="Increase amount"
                disabled={step >= (packs?.length ?? 0) - 1 || busy}
                onClick={() =>
                  setStep((current) => Math.min((packs?.length ?? 1) - 1, current + 1))
                }
              >
                <Icon name="fa-plus" />
              </button>
            </div>
            <p className="s-credits-pack-note">
              {pack.total_credits.toLocaleString()} credits · about{" "}
              {pack.songs_equivalent.toLocaleString()} songs
            </p>
            <p className="s-credits-accent">Better value than one-time credit packs</p>
          </>
        ) : null}

        <div className="s-credits-switch-row">
          <label id={switchLabelId} htmlFor="credits-auto-reload">
            Turn on auto-reload
          </label>
          <Switch
            id="credits-auto-reload"
            checked={autoReload}
            disabled={!AUTO_RELOAD_SUPPORTED}
            aria-labelledby={switchLabelId}
            aria-describedby={AUTO_RELOAD_SUPPORTED ? undefined : switchNoteId}
            title={
              AUTO_RELOAD_SUPPORTED
                ? "Top up automatically when credits run low"
                : "Auto-reload isn't configured for this account yet"
            }
            onCheckedChange={toggleAutoReload}
          />
        </div>
        {AUTO_RELOAD_SUPPORTED ? null : (
          <p id={switchNoteId} className="s-note s-credits-switch-note">
            Auto-reload isn&apos;t configured yet — buy a pack to top up now.
          </p>
        )}

        {loadError ? (
          <p className="s-error" role="alert">
            {loadError}
          </p>
        ) : null}
        {checkoutError ? (
          <p className="s-error" role="alert">
            {checkoutError}
          </p>
        ) : null}

        <button
          type="button"
          className="s-credits-buy"
          disabled={!pack || busy}
          onClick={() => void startCheckout()}
        >
          {busy ? "Opening checkout…" : "Buy credits"}
        </button>
        <button type="button" className="s-credits-not-now" onClick={onClose} disabled={busy}>
          Not now
        </button>
      </div>
    </div>
  );
}
