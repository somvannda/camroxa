'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { ExternalLink, Loader2, QrCode, X } from 'lucide-react';

type CutluyCheckoutModalProps = {
  isOpen: boolean;
  checkoutUrl: string | null;
  title?: string;
  planName?: string;
  planPrice?: string;
  onClose: () => void;
};

export default function CutluyCheckoutModal({
  isOpen,
  checkoutUrl,
  title = 'Complete payment with KHQR',
  planName,
  planPrice,
  onClose,
}: CutluyCheckoutModalProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted || !isOpen || !checkoutUrl) return null;

  const heading = planName ? `Pay for ${planName}` : title;

  const modal = (
    <div
      className="fixed inset-0 z-[220] flex items-center justify-center bg-black/80 p-3 backdrop-blur-sm sm:p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="cutluy-checkout-title"
    >
      <div
        className="relative flex w-full max-w-[360px] flex-col overflow-hidden rounded-3xl border border-white/10 bg-slate-900 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-white/10 px-4 py-3 sm:px-5 sm:py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <QrCode className="h-5 w-5 shrink-0 text-fuchsia-300" />
              <h2 id="cutluy-checkout-title" className="truncate text-base font-semibold text-white sm:text-lg">
                {heading}
              </h2>
            </div>
            {planPrice ? (
              <p className="mt-1 pl-7 text-sm text-slate-400">
                {planPrice} · Scan the KHQR code below
              </p>
            ) : (
              <p className="mt-1 pl-7 text-sm text-slate-400">Scan the KHQR code below</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-full p-2 text-slate-400 transition hover:bg-white/10 hover:text-white"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="bg-white/[0.02] px-4 py-3 sm:px-5">
          <div className="relative mx-auto h-[320px] w-full max-w-[320px] overflow-hidden rounded-2xl border border-white/10 bg-white shadow-inner">
            <iframe
              title="CutLuy KHQR checkout"
              src={checkoutUrl}
              className="pointer-events-auto absolute left-1/2 top-0 h-[580px] w-[390px] -translate-x-1/2 origin-top scale-[0.55] border-0 bg-white"
              scrolling="no"
            />
          </div>
          <div className="mt-3 flex items-center justify-between gap-3 text-xs sm:text-sm">
            <p className="text-slate-400">Secure payment via CutLuy</p>
            <a
              href={checkoutUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex shrink-0 items-center gap-1 text-fuchsia-200 hover:text-white"
            >
              Open full page
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>

        <div className="border-t border-white/10 px-4 py-3 text-center sm:px-5">
          <div className="inline-flex items-center gap-2 text-xs text-slate-400 sm:text-sm">
            <Loader2 className="h-4 w-4 animate-spin text-violet-400" />
            Waiting for payment confirmation…
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
