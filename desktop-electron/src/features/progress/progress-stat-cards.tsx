import { Card } from "../../components/card";
import { formatCount } from "../../lib/format";
import type { ProgressStats } from "./progress-format";

const CARDS = [
  { key: "active", label: "Active runs", testId: "progress-stat-active" },
  { key: "video", label: "Converter / merger", testId: "progress-stat-video" },
  { key: "waiting", label: "Waiting on user", testId: "progress-stat-waiting" },
  { key: "failed", label: "Failed / blocked", testId: "progress-stat-failed" },
] as const;

/** PG-09…PG-13: label + figure only, no decorative icon. */
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
        <Card key={card.key} className="px-4 py-3" data-testid={card.testId}>
          <p className="text-meta text-text-muted">{card.label}</p>
          <p className="mt-1 text-[28px] font-semibold leading-8 text-text-primary text-tabular">
            {loading ? "--" : formatCount(stats[card.key])}
          </p>
        </Card>
      ))}
    </div>
  );
}
