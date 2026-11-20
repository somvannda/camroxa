import { createElement } from "react";
import { Dialog, DialogContent } from "../../components/dialog";

interface CheckoutDialogProps {
  open: boolean;
  url: string | null;
  onClose: () => void;
}

/**
 * In-app ChmabaPay checkout. The provider page runs in a sandboxed `<webview>`
 * inside our Dialog, so the user never leaves Camxora and no separate browser
 * window appears.
 */
export function CheckoutDialog({ open, url, onClose }: CheckoutDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent
        title="Complete payment"
        description="Scan the KHQR code or pay in the provider page. This closes automatically when credits arrive."
        className="max-w-[460px]"
      >
        <div className="h-[520px] overflow-hidden rounded-control border border-border bg-white">
          {url
            ? createElement("webview", {
                src: url,
                style: { width: "100%", height: "100%", border: "0" },
                webpreferences: "contextIsolation=yes,nodeIntegration=no,sandbox=yes",
              })
            : null}
        </div>
        <div className="mt-2 flex items-center justify-between gap-2 text-caption text-text-muted">
          <span>Payments are processed by ChmabaPay.</span>
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
