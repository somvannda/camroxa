import { Card } from "../../components/card";
import { Icon } from "../../components/icon";
import { Badge } from "../../components/status";
import { activityIcon, activityTone, type ActivityRow } from "./dashboard-format";

interface RecentActivityCardProps {
  rows: ActivityRow[];
  loading: boolean;
}

interface ActivityGroup {
  label: string;
  rows: ActivityRow[];
}

function groupRows(rows: ActivityRow[]): ActivityGroup[] {
  const groups: ActivityGroup[] = [];
  for (const row of rows) {
    const last = groups[groups.length - 1];
    if (last && last.label === row.group) last.rows.push(row);
    else groups.push({ label: row.group, rows: [row] });
  }
  return groups;
}

export function RecentActivityCard({ rows, loading }: RecentActivityCardProps) {
  const groups = groupRows(rows);

  return (
    <Card className="p-5" data-testid="recent-activity">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-title font-semibold text-text-primary">Recent Activity</h2>
          <p className="mt-1 text-body text-text-secondary">
            The latest runs, renders and uploads on this account.
          </p>
        </div>
        {rows.length > 0 ? (
          <Badge tone="neutral">{rows.length} events</Badge>
        ) : null}
      </div>

      <div className="mt-4">
        {loading ? (
          <div className="space-y-2" aria-hidden="true">
            {[0, 1, 2, 3].map((index) => (
              <div key={index} className="h-12 rounded-control bg-surface-2" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-control border border-dashed border-border px-6 py-10 text-center">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-2 text-text-muted">
              <Icon name="fa-bolt" size={16} />
            </span>
            <p className="mt-3 text-body font-medium text-text-primary">Nothing here yet</p>
            <p className="mt-1 max-w-md text-meta text-text-secondary">
              No recent activity found. Generate a song, render a video or upload to YouTube and
              it will appear here.
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {groups.map((group) => (
              <section key={group.label}>
                <h3 className="text-caption font-medium uppercase tracking-wide text-text-muted">
                  {group.label}
                </h3>
                <ul className="mt-2 divide-y divide-border">
                  {group.rows.map((row) => (
                    <li key={row.key} className="flex items-start gap-3 py-2.5">
                      <span
                        className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-surface-2 text-text-secondary"
                        aria-hidden="true"
                      >
                        <Icon name={activityIcon(row.kind)} size={14} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-body font-medium text-text-primary">{row.kind}</p>
                          <Badge tone={activityTone(row.status)}>{row.status}</Badge>
                        </div>
                        <p
                          className="mt-0.5 truncate text-meta text-text-secondary"
                          title={row.detail}
                        >
                          {row.detail}
                        </p>
                      </div>
                      <time
                        className="shrink-0 pt-0.5 text-caption text-text-muted text-tabular"
                        dateTime={row.timestamp}
                        title={row.timestamp}
                      >
                        {row.time}
                      </time>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
