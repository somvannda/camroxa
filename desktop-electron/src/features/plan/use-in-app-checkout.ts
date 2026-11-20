import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../../lib/api";

export interface PaymentStatus {
  status: string;
  fulfilled: boolean;
  pack_name: string;
  credits: number;
}

export interface CheckoutSession {
  paymentId: string;
  checkoutUrl: string;
  packName: string;
  qrString: string;
  amountCents: number;
  expiresAt: string;
}

const POLL_INTERVAL_MS = 3_000;
const MAX_ATTEMPTS = 100;

/**
 * Tracks a top-up checkout inside the app.
 *
 * The QR is rendered natively from the provider payload; the webview is only a
 * fallback for a provider that does not return a KHQR string.
 */
export function useInAppCheckout(onFulfilled: (status: PaymentStatus) => void) {
  const [pending, setPending] = useState<CheckoutSession | null>(null);
  const [state, setState] = useState<"idle" | "waiting" | "fulfilled" | "failed" | "timeout">(
    "idle",
  );
  const fulfilledRef = useRef(onFulfilled);
  fulfilledRef.current = onFulfilled;

  const start = useCallback((session: CheckoutSession) => {
    if (!/^https:\/\//i.test(session.checkoutUrl) && !session.qrString) {
      throw new Error("The checkout link is not a secure web address.");
    }
    setPending(session);
    setState("waiting");
  }, []);

  const close = useCallback(() => {
    setPending(null);
    setState("idle");
  }, []);

  useEffect(() => {
    if (!pending) return;
    let cancelled = false;
    let attempts = 0;
    let timer: number | null = null;

    const poll = async () => {
      try {
        const status = await apiRequest<PaymentStatus>({
          method: "GET",
          path: `/topups/payments/${encodeURIComponent(pending.paymentId)}`,
          apiVersion: "v3",
        });
        if (cancelled) return;
        if (status.fulfilled) {
          setState("fulfilled");
          setPending(null);
          fulfilledRef.current(status);
          return;
        }
        const key = status.status.toLowerCase();
        if (["failed", "expired", "cancelled"].includes(key)) {
          setState("failed");
          setPending(null);
          return;
        }
      } catch {
        // A poll error keeps waiting; the account refresh is the final truth.
      }
      attempts += 1;
      if (attempts >= MAX_ATTEMPTS) {
        setState("timeout");
        setPending(null);
        return;
      }
      if (!cancelled) timer = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
    };

    timer = window.setTimeout(() => void poll(), 2_000);
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [pending]);

  return { pending, state, start, close };
}
