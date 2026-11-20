import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../../lib/api";

export interface PaymentStatus {
  status: string;
  fulfilled: boolean;
  pack_name: string;
  credits: number;
}

interface PendingPayment {
  id: string;
  packName: string;
}

const POLL_INTERVAL_MS = 3_000;
const MAX_ATTEMPTS = 100;

/**
 * Opens the provider checkout in the app's modal window and polls the top-up
 * payment until it is fulfilled. The renderer never leaves the app.
 */
export function useInAppCheckout(onFulfilled: (status: PaymentStatus) => void) {
  const [pending, setPending] = useState<PendingPayment | null>(null);
  const [state, setState] = useState<"idle" | "waiting" | "fulfilled" | "failed" | "timeout">(
    "idle",
  );
  const fulfilledRef = useRef(onFulfilled);
  fulfilledRef.current = onFulfilled;

  const start = useCallback(
    async (checkoutUrl: string, paymentId: string, packName: string) => {
      const opened = await window.camxora.checkout.open({ url: checkoutUrl });
      if (!opened.ok) throw new Error(opened.error.message);
      setPending({ id: paymentId, packName });
      setState("waiting");
    },
    [],
  );

  const close = useCallback(async () => {
    await window.camxora.checkout.close();
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
          path: `/topups/payments/${encodeURIComponent(pending.id)}`,
          apiVersion: "v3",
        });
        if (cancelled) return;
        if (status.fulfilled) {
          setState("fulfilled");
          setPending(null);
          await window.camxora.checkout.close();
          fulfilledRef.current(status);
          return;
        }
        const key = status.status.toLowerCase();
        if (["failed", "expired", "cancelled"].includes(key)) {
          setState("failed");
          setPending(null);
          await window.camxora.checkout.close();
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
