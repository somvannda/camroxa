import { AlertTriangle } from "lucide-react";
import { Button } from "../../components/button";

interface ProgressErrorBannerProps {
  stale: boolean;
  lastLoadedLabel: string | null;
  onRetry: () => void;
}

export function progressErrorMessage(stale: boolean): string {
  return stale
    ? "Unable to load progress rows. The last loaded rows are still shown. Check your connection and retry."
    : "Unable to load progress rows. No rows are available yet. Check your connection and retry.";
}

/** PG-49: the banner sits above the table and never replaces retained rows. */
export function ProgressErrorBanner({
  stale,
  lastLoadedLabel,
  onRetry,
}: ProgressErrorBannerProps) {
  return (
    <div
      className="flex items-start gap-3 rounded-card border border-danger/30 bg-danger-soft px-4 py-3"
      role="alert"
      data-testid="progress-error-banner"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-body text-danger">{progressErrorMessage(stale)}</p>
        {stale && lastLoadedLabel ? (
          <p className="mt-0.5 font-mono text-caption text-danger/80">
            Stale · last updated {lastLoadedLabel}
          </p>
        ) : null}
      </div>
      <Button variant="secondary" onClick={onRetry} data-testid="progress-error-retry">
        Retry
      </Button>
    </div>
  );
}
