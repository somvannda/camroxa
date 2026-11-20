import { Card } from "../../components/card";
import { Badge } from "../../components/status";
import { Icon } from "../../components/icon";
import type { DashboardStats } from "../dashboard/account-types";
import {
  activityIcon,
  activityRows,
  activityTone,
} from "../dashboard/dashboard-format";
import { profileCounters } from "./profile-format";

export function ActivityCard({ stats }: { stats: DashboardStats | null | undefined }) {
  const counters = profileCounters(stats);
  const events = activityRows(stats, 6);

  return (
    <Card className="p-4" data-testid="profile-activity">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-title font-semibold text-text-primary">Activity</h2>
        <span className="text-caption text-text-muted">Latest first</span>
      </div>

      <div className="mt-2">
        {events.length === 0 ? (
          <p className="rounded-control border border-dashed border-border px-3 py-4 text-meta text-text-secondary">
            No recent activity yet. Generate a song or render a video to see it here.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {events.map((row) => (
              <li key={row.key} className="flex items-start gap-2 py-2">
                <span
                  className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-control bg-surface-2 text-text-secondary"
                  aria-hidden="true"
                >
                  <Icon name={activityIcon(row.kind)} size={11} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <p className="text-meta font-medium text-text-primary">{row.kind}</p>
                    <Badge tone={activityTone(row.status)}>{row.status}</Badge>
                  </div>
                  <p className="truncate text-caption text-text-secondary" title={row.detail}>
                    {row.detail}
                  </p>
                </div>
                <time className="shrink-0 pt-0.5 text-caption text-text-muted" dateTime={row.timestamp}>
                  {row.time}
                </time>
              </li>
            ))}
          </ul>
        )}
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 border-t border-border pt-3">
        {counters.map((counter) => (
          <div key={counter.label} className="rounded-control bg-surface-2 px-2.5 py-1.5">
            <dt className="text-caption text-text-muted">{counter.label}</dt>
            <dd className="text-meta font-medium text-text-primary text-tabular">
              {counter.value}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
