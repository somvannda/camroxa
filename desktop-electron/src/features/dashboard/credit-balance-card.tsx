import { Card } from "../../components/card";
import { Badge } from "../../components/status";
import { formatCount } from "../../lib/format";
import type { CreditPosition } from "./dashboard-format";

interface CreditBalanceCardProps {
  position: CreditPosition | null;
}

export function CreditBalanceCard({ position }: CreditBalanceCardProps) {
  const loading = !position;

  return (
    <Card className="flex flex-col p-5" data-testid="credit-balance">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-title font-semibold text-text-primary">Credit balance</h2>
          <p className="mt-1 text-body text-text-secondary">
            Every generation is paid from your credit wallet.
          </p>
        </div>
        <Badge tone="accent">
          <span className="whitespace-nowrap">Credits only</span>
        </Badge>
      </div>

      <div className="mt-5">
        <p className="text-caption text-text-muted">Available now</p>
        <p
          className="mt-1 text-[36px] font-semibold leading-10 text-text-primary text-tabular"
          data-testid="credit-balance-value"
        >
          {loading ? "--" : formatCount(position.balance)}
        </p>
        <p className="text-meta text-text-secondary">
          {loading
            ? "Loading your wallet…"
            : `${formatCount(position.spent)} of ${formatCount(position.total)} credits used`}
        </p>
      </div>

      <div
        className="mt-3 h-2 overflow-hidden rounded-full bg-surface-3"
        role="progressbar"
        aria-label="Credits used"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={position?.percentUsed ?? 0}
      >
        <div
          className="h-full rounded-full bg-[image:var(--brand-gradient)]"
          style={{ width: `${position?.percentUsed ?? 0}%` }}
        />
      </div>

      <dl className="mt-4 space-y-1.5">
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-meta text-text-secondary">Credits granted</dt>
          <dd className="text-meta text-text-primary text-tabular">
            {loading ? "--" : formatCount(position.total)}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-meta text-text-secondary">Credits spent</dt>
          <dd className="text-meta text-text-primary text-tabular" data-testid="credit-spent">
            {loading ? "--" : formatCount(position.spent)}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-meta text-text-secondary">Credits remaining</dt>
          <dd className="text-meta font-medium text-text-primary text-tabular">
            {loading ? "--" : formatCount(position.balance)}
          </dd>
        </div>
      </dl>

      <div className="mt-4 grid grid-cols-2 gap-2 border-t border-border pt-4">
        <div className="rounded-control bg-surface-2 px-3 py-2">
          <p className="text-caption text-text-muted">Studio exports</p>
          <p className="text-body font-medium text-text-primary text-tabular">
            {loading ? "--" : formatCount(position.studioExports)}
          </p>
        </div>
        <div className="rounded-control bg-surface-2 px-3 py-2">
          <p className="text-caption text-text-muted">Manual exports</p>
          <p className="text-body font-medium text-text-primary text-tabular">
            {loading ? "--" : formatCount(position.manualExports)}
          </p>
        </div>
        <div className="rounded-control bg-surface-2 px-3 py-2">
          <p className="text-caption text-text-muted">YouTube uploads</p>
          <p className="text-body font-medium text-text-primary text-tabular">
            {loading ? "--" : formatCount(position.youtubeUploads)}
          </p>
        </div>
        <div className="rounded-control bg-surface-2 px-3 py-2">
          <p className="text-caption text-text-muted">Last export</p>
          <p className="truncate text-meta font-medium text-text-primary" title={position?.lastExport}>
            {loading ? "--" : position.lastExport}
          </p>
        </div>
      </div>
    </Card>
  );
}
