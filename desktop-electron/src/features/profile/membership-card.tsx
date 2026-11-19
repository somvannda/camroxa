import { Card } from "../../components/card";
import type { DashboardStats, LicenseInfo, UserMe } from "../dashboard/account-types";
import { formatPlanName } from "../dashboard/dashboard-format";
import {
  membershipFields,
  membershipMetrics,
  planSubtitle,
  type ProfileMetric,
} from "./profile-format";

const BAR_COLORS: Record<ProfileMetric["tone"], string> = {
  emerald: "var(--success)",
  sky: "var(--info)",
};

const LOADING_METRICS: ProfileMetric[] = [
  { key: "profiles", label: "Profiles", value: "--", percent: 0, tone: "emerald" },
  { key: "songs", label: "Songs", value: "--", percent: 0, tone: "sky" },
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
  const fields = membershipFields(me, stats, license);
  const formattedPlan = formatPlanName(me?.plan_name);
  const planName = loading ? "--" : formattedPlan === "No plan" ? "No active plan" : formattedPlan;

  return (
    <Card className="p-5" data-testid="profile-membership">
      <h2 className="text-title font-semibold text-text-primary">Membership</h2>

      <div className="mt-4">
        <p className="text-[20px] font-semibold leading-7 text-text-primary">{planName}</p>
        {loading ? (
          <p className="text-meta text-text-secondary">Loading plan details...</p>
        ) : me?.plan_name?.trim() ? (
          <p className="text-meta text-text-secondary">{planSubtitle(me.plan_name)}</p>
        ) : null}
      </div>

      <div className="mt-5 space-y-4">
        {metrics.map((metric) => (
          <div key={metric.key}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-meta text-text-secondary">{metric.label}</span>
              <span className="text-meta font-medium text-text-primary text-tabular">
                {metric.value}
              </span>
            </div>
            <div
              className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3"
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

      <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-border pt-4">
        {fields.map((field) => (
          <div key={field.label}>
            <dt className="text-caption text-text-muted">{field.label}</dt>
            <dd className="mt-0.5 truncate text-body text-text-primary text-tabular">
              {loading ? "--" : field.value}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
