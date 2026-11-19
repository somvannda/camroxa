import { AlertTriangle, X } from "lucide-react";

export function MusicErrorBanner({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss?: () => void;
}) {
  return (
    <div
      className="flex items-start gap-3 rounded-card border border-danger/30 bg-danger-soft px-4 py-3"
      role="alert"
      data-testid="music-error"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
      <p className="flex-1 text-body text-danger">{message}</p>
      {onDismiss ? (
        <button
          type="button"
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] text-danger/80 hover:bg-danger/10 hover:text-danger"
          aria-label="Dismiss"
          onClick={onDismiss}
        >
          <X size={14} />
        </button>
      ) : null}
    </div>
  );
}
