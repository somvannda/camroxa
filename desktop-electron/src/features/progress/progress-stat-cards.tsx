import { Card } from "../../components/card";
import { formatCount } from "../../lib/format";
import type { ProgressStats } from "./progress-format";

const CARDS = [
  { key: "active", label: "Active runs", testId: "progress-stat-active", accent: "var(--accent)" },
  { key: "video", label: "Renders", testId: "progress-stat-video", accent: "var(--info)" },
  { key: "waiting", label: "Waiting on user", testId: "progress-stat-waiting", accent: "var(--warning)" },
  { key: "failed", label: "Failed / blocked", testId: "progress-stat-failed", accent: "var(--danger)" },
] as const;

/** Compact label + figure cards with a semantic accent bar, like the desktop app. */
export function ProgressStatCards({
  stats,
  loading,
}: {
  stats: ProgressStats;
  loading: boolean;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4" data-testid="progress-stats">
      {CARDS.map((card) => (
        <Card key={card.key} className="overflow-hidden px-3 py-2" data-testid={card.testId}>
          <span
            className="mb-1.5 block h-0.5 w-6 rounded-full"
            style={{ backgroundColor: card.accent }}
            aria-hidden="true"
          />
          <p className="text-caption text-text-muted">{card.label}</p>
          <p className="text-[20px] font-semibold leading-6 text-text-primary text-tabular">
            {loading ? "--" : formatCount(stats[card.key])}
          </p>
        </Card>
      ))}
    </div>
  );
}
