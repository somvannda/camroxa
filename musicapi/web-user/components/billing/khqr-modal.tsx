"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch, backendUrl } from "@/lib/api";

/**
 * Inline KHQR checkout. Instead of redirecting the payer to ChmabaPay's hosted
 * checkout, this renders the KHQR code the provider issued for the transaction
 * and polls our own status route (which reconciles against ChmabaPay) until the
 * code settles or dies.
 */

interface CheckoutStatus {
  transaction_id: string;
  status: string;
  credits: number;
  currency: string;
  amount: number;
  paid_at: string | null;
  expires_at: string | null;
  error: string | null;
}

interface Props {
  transactionId: string;
  credits: number;
  currency: string;
  amount: number;
  expiresAt: string | null;
  onPaid: () => void;
  onClose: () => void;
}

const SCANNED = new Set(["scanned"]);
const DEAD = new Set(["expired", "failed", "refunded", "cancelled"]);

function secondsUntil(iso: string | null): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.ceil((t - Date.now()) / 1000));
}

function formatClock(total: number): string {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function KhqrModal({ transactionId, credits, currency, amount, expiresAt, onPaid, onClose }: Props) {
  const [status, setStatus] = useState("pending");
  const [error, setError] = useState("");
  const [secondsLeft, setSecondsLeft] = useState<number | null>(() => secondsUntil(expiresAt));
  const [qrFailed, setQrFailed] = useState(false);

  // Keep the latest callbacks without re-arming the poll every render.
  const onPaidRef = useRef(onPaid);
  const onCloseRef = useRef(onClose);
  const paidRef = useRef(false);

  useEffect(() => {
    onPaidRef.current = onPaid;
    onCloseRef.current = onClose;
  }, [onPaid, onClose]);

  // Countdown to the code's expiry (ABA's window is ~180s).
  useEffect(() => {
    const t = window.setInterval(() => setSecondsLeft(secondsUntil(expiresAt)), 1000);
    return () => window.clearInterval(t);
  }, [expiresAt]);

  // Poll until the code settles or dies. The backend reconciles with ChmabaPay
  // and credits exactly once, so a missed webhook still lands.
  useEffect(() => {
    let active = true;
    let timer: number | undefined;

    async function poll() {
      try {
        const s = await apiFetch<CheckoutStatus>(`/payments/chmaba/status/${transactionId}`);
        if (!active) return;
        setStatus(s.status);
        if (s.status === "paid") {
          if (!paidRef.current) {
            paidRef.current = true;
            onPaidRef.current();
          }
          return; // stop polling
        }
        if (DEAD.has(s.status)) return; // stop polling
      } catch (e) {
        if (!active) return;
        // A 404 means the transaction is gone; anything else is transient.
        if (e instanceof Error && /not found/i.test(e.message)) {
          setError(e.message);
          return;
        }
      }
      if (active) timer = window.setTimeout(poll, 3000);
    }

    timer = window.setTimeout(poll, 1500);
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [transactionId]);

  // Close automatically a moment after a successful payment.
  useEffect(() => {
    if (status !== "paid") return;
    const t = window.setTimeout(() => onCloseRef.current(), 2500);
    return () => window.clearTimeout(t);
  }, [status]);

  // Escape dismisses the modal while the code is still live.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && status !== "paid") onCloseRef.current();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [status]);

  const paid = status === "paid";
  const dead = DEAD.has(status);
  const scanned = SCANNED.has(status);
  const expired = !paid && (status === "expired" || secondsLeft === 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={() => {
        if (!paid) onClose();
      }}
    >
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div className="glass relative w-full max-w-sm rounded-2xl p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={() => onClose()}
          aria-label="Close"
          className="absolute right-3 top-3 inline-flex h-8 w-8 items-center justify-center rounded-lg text-white/50 hover:bg-white/10 hover:text-white"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>

        <div className="text-center">
          <h2 className="text-lg font-semibold text-white">Scan to pay</h2>
          <p className="mt-2 text-3xl font-extrabold text-white">
            {currency}{" "}
            {amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-sm text-white/50">for {credits.toLocaleString()} credits</p>
        </div>

        <div className="mt-5 flex justify-center">
          <div className="rounded-xl bg-white p-3">
            {paid ? (
              <div className="flex h-52 w-52 flex-col items-center justify-center gap-2 text-emerald-600">
                <svg viewBox="0 0 24 24" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                <span className="text-sm font-semibold">Payment received</span>
              </div>
            ) : qrFailed || dead ? (
              <div className="flex h-52 w-52 items-center justify-center px-4 text-center text-xs text-neutral-500">
                {qrFailed ? "Could not load the QR code. Close and try again." : "This code is no longer payable."}
              </div>
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={backendUrl(`/payments/chmaba/qr/${transactionId}`)}
                alt="KHQR code"
                width={208}
                height={208}
                className={`h-52 w-52 ${expired ? "opacity-25" : ""}`}
                onError={() => setQrFailed(true)}
              />
            )}
          </div>
        </div>

        <div className="mt-4 text-center text-sm">
          {paid && <p className="font-medium text-[var(--emerald)]">Credits added to your account.</p>}
          {!paid && scanned && <p className="font-medium text-white/80">Payment detected — confirming…</p>}
          {!paid && !scanned && expired && (
            <p className="font-medium text-red-300">This code has expired. Close and start a new payment.</p>
          )}
          {!paid && !scanned && !expired && <p className="text-white/60">Open your banking app and scan the KHQR code.</p>}
        </div>

        {!paid && !dead && (
          <div className="mt-3 flex items-center justify-center gap-2 text-xs text-white/50">
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white/80" />
            {scanned
              ? "Confirming payment…"
              : secondsLeft !== null
                ? `Expires in ${formatClock(secondsLeft)}`
                : "Waiting for payment…"}
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-center text-sm text-red-300">
            {error}
          </div>
        )}

        <button
          type="button"
          onClick={() => onClose()}
          className="mt-5 w-full rounded-lg border border-white/10 bg-white/[0.03] py-2 text-sm font-medium text-white/80 transition hover:bg-white/10"
        >
          {paid ? "Done" : "Cancel"}
        </button>
      </div>
    </div>
  );
}
