import { Card } from "../../components/card";
import type { DashboardStats, LicenseInfo, UserMe } from "../dashboard/account-types";
import { formatCredits } from "../../lib/format";
import {
  membershipFields,
  membershipMetrics,
  type ProfileMetric,
} from "./profile-format";

const BAR_COLORS: Record<ProfileMetric["tone"], string> = {
  emerald: "var(--success)",
  sky: "var(--info)",
};

const LOADING_METRICS: ProfileMetric[] = [
  { key: "profiles", label: "Profiles", value: "--", percent: 0, tone: "emerald" },
  { key: "credits", label: "Credits used", value: "--", percent: 0, tone: "sky" },
];

interface MembershipCardProps {
  me: UserMe | null | undefined;
  stats: DashboardStats | null | undefined;
  license: LicenseInfo | null | undefined;
  profileCount: number;
  loading: boolean;
}

export function MembershipCard({
  me,
  stats,
  license,
  profileCount,
  loading,
}: MembershipCardProps) {
  const metrics = loading ? LOADING_METRICS : membershipMetrics(me, stats, license, profileCount);
  const fields = membershipFields(me, stats);

  return (
    <Card className="p-4" data-testid="profile-membership">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-title font-semibold text-text-primary">Credits & usage</h2>
        <span className="text-caption text-text-muted">Credits only</span>
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <p className="text-[28px] font-semibold leading-8 text-text-primary text-tabular">
          {loading ? "--" : formatCredits(me?.credit_balance ?? 0)}
        </p>
        <p className="text-meta text-text-secondary">credits available</p>
      </div>

      <div className="mt-3 space-y-3">
        {metrics.map((metric) => (
          <div key={metric.key}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-meta text-text-secondary">{metric.label}</span>
              <span className="text-meta font-medium text-text-primary text-tabular">
                {metric.value}
              </span>
            </div>
            <div
              className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-3"
              role="progressbar"
              aria-label={`${metric.label} used`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={metric.percent}
            >
              <div
                className="h-full rounded-full"
                style={{ width: `${metric.percent}%`, backgroundColor: BAR_COLORS[metric.tone] }}
              />
            </div>
          </div>
        ))}
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-border pt-3">
        {fields.map((field) => (
          <div key={field.label}>
            <dt className="text-caption text-text-muted">{field.label}</dt>
            <dd className="mt-0.5 truncate text-meta text-text-primary text-tabular">
              {loading ? "--" : field.value}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
