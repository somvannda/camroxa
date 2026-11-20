import { createElement } from "react";
import { Dialog, DialogContent } from "../../components/dialog";
import { formatCredits } from "../../lib/format";
import type { CheckoutSession } from "./use-in-app-checkout";

const CHMABA_QR_RENDERER = "https://pay.chmaba.com/api/v1/khqr/render.svg";

function formatMoney(cents: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);
}

interface CheckoutDialogProps {
  session: CheckoutSession | null;
  credits: number;
  onClose: () => void;
}

/**
 * Compact in-app ChmabaPay checkout.
 *
 * When the provider returns a KHQR payload we render the QR directly (provider
 * SVG renderer) so it fits the dialog with no scrolling. A webview is only the
 * fallback for providers that return no QR payload.
 */
export function CheckoutDialog({ session, credits, onClose }: CheckoutDialogProps) {
  const qrUrl = session?.qrString
    ? `${CHMABA_QR_RENDERER}?payload=${encodeURIComponent(session.qrString)}`
    : null;

  return (
    <Dialog open={Boolean(session)} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent
        title="Scan to pay"
        description={
          session ? `${session.packName} · ${formatMoney(session.amountCents)}` : undefined
        }
        className="!max-w-[340px] !p-4 text-center"
      >
        {qrUrl ? (
          <div className="mx-auto w-fit rounded-card border border-border bg-white p-3">
            <img
              src={qrUrl}
              alt="KHQR payment code"
              width={232}
              height={232}
              className="block h-[232px] w-[232px]"
            />
          </div>
        ) : session ? (
          <div className="h-[360px] overflow-hidden rounded-control border border-border bg-white">
            {createElement("webview", {
              src: session.checkoutUrl,
              style: { width: "100%", height: "100%", border: "0" },
              zoomfactor: "0.75",
              webpreferences: "contextIsolation=yes,nodeIntegration=no,sandbox=yes",
            })}
          </div>
        ) : null}

        <p className="mt-3 text-meta text-text-secondary">
          Open any KHQR-enabled banking app and scan the code.
        </p>
        <p className="mt-1 text-caption text-text-muted">
          {formatCredits(credits)} credits · closes automatically when paid
        </p>
        <div className="mt-3 flex items-center justify-between gap-2 border-t border-border pt-2 text-[10px] text-text-muted">
          <span>Secured by ChmabaPay</span>
          <button
            type="button"
            className="text-caption text-text-secondary hover:text-text-primary"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
