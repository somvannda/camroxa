import { Card } from "../../components/card";
import type { DashboardStats } from "../dashboard/account-types";
import { profileCounters } from "./profile-format";

export function ActivityCard({ stats }: { stats: DashboardStats | null | undefined }) {
  const counters = profileCounters(stats);

  return (
    <Card className="p-5" data-testid="profile-activity">
      <h2 className="text-title font-semibold text-text-primary">Activity</h2>
      <p className="mt-1 text-body text-text-secondary">Lifetime counters for this account.</p>

      <dl className="mt-5 grid grid-cols-2 gap-4">
        {counters.map((counter) => (
          <div key={counter.label} className="rounded-control border border-border bg-surface-2 p-3">
            <dt className="text-caption text-text-muted">{counter.label}</dt>
            <dd className="mt-1 text-[22px] font-semibold leading-7 text-text-primary text-tabular">
              {counter.value}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
