import { Icon } from "../../components/icon";
import { Card } from "../../components/card";
import { classNames } from "../../lib/format";
import type { KpiValue } from "./dashboard-format";

const ICONS: Record<KpiValue["key"], string> = {
  balance: "fa-wallet",
  spent: "fa-coins",
  songs: "fa-music",
  images: "fa-image",
  videos: "fa-video",
  uploads: "fa-cloud-arrow-up",
};

const TINTS: Record<KpiValue["key"], string> = {
  balance: "bg-accent-soft text-accent",
  spent: "bg-warning-soft text-warning",
  songs: "bg-info-soft text-info",
  images: "bg-success-soft text-success",
  videos: "bg-danger-soft text-danger",
  uploads: "bg-surface-3 text-text-secondary",
};

export function KpiCard({ item }: { item: KpiValue }) {
  return (
    <Card className="flex items-start justify-between gap-3 p-4" data-testid={`kpi-${item.key}`}>
      <div className="min-w-0">
        <p className="text-meta leading-4 text-text-muted">{item.label}</p>
        <p className="mt-1 text-[26px] font-semibold leading-8 text-text-primary text-tabular">
          {item.value}
        </p>
        {item.hint ? (
          <p className="mt-0.5 truncate text-caption text-text-muted" title={item.hint}>
            {item.hint}
          </p>
        ) : null}
      </div>
      <span
        className={classNames(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-control",
          TINTS[item.key],
        )}
        aria-hidden="true"
      >
        <Icon name={ICONS[item.key]} size={16} />
      </span>
    </Card>
  );
}
