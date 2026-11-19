import { Coins, Image, Music2, UploadCloud, Video, type LucideIcon } from "lucide-react";
import { Card } from "../../components/card";
import { classNames } from "../../lib/format";
import type { KpiValue } from "./dashboard-format";

const ICONS: Record<KpiValue["key"], LucideIcon> = {
  credits: Coins,
  songs: Music2,
  images: Image,
  videos: Video,
  youtube: UploadCloud,
};

const TINTS: Record<KpiValue["key"], string> = {
  credits: "bg-accent-soft text-accent",
  songs: "bg-info-soft text-info",
  images: "bg-success-soft text-success",
  videos: "bg-warning-soft text-warning",
  youtube: "bg-danger-soft text-danger",
};

export function KpiCard({ item }: { item: KpiValue }) {
  const Icon = ICONS[item.key];
  return (
    <Card className="flex items-start justify-between gap-3 p-4" data-testid={`kpi-${item.key}`}>
      <div className="min-w-0">
        <p className="truncate text-meta text-text-muted">{item.label}</p>
        <p className="mt-1 text-[28px] font-semibold leading-8 text-text-primary text-tabular">
          {item.value}
        </p>
      </div>
      <span
        className={classNames(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-control",
          TINTS[item.key],
        )}
        aria-hidden="true"
      >
        <Icon size={16} strokeWidth={1.5} />
      </span>
    </Card>
  );
}
