import { Card } from "../../components/card";
import type { QuotaRow, SummaryLine } from "./dashboard-format";

const BAR_COLORS: Record<QuotaRow["tone"], string> = {
  violet: "var(--accent)",
  sky: "var(--info)",
  emerald: "var(--success)",
};

interface RemainingMonthCardProps {
  rows: QuotaRow[];
  summary: SummaryLine[];
}

export function RemainingMonthCard({ rows, summary }: RemainingMonthCardProps) {
  return (
    <Card className="flex flex-col p-5" data-testid="remaining-month">
      <div>
        <h2 className="text-title font-semibold text-text-primary">Remaining This Month</h2>
        <p className="mt-1 text-body text-text-secondary">
          Remaining against your current plan allowance.
        </p>
      </div>

      <div className="mt-5 space-y-4">
        {rows.map((row) => (
          <div key={row.key}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-body text-text-secondary">{row.label}</span>
              <span className="text-body font-medium text-text-primary text-tabular">
                {row.value}
              </span>
            </div>
            <div
              className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3"
              role="progressbar"
              aria-label={`${row.label} remaining`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={row.percent}
            >
              <div
                className="h-full rounded-full"
                style={{ width: `${row.percent}%`, backgroundColor: BAR_COLORS[row.tone] }}
              />
            </div>
            <p className="mt-1 text-caption text-text-muted text-tabular">{row.percent}%</p>
          </div>
        ))}
      </div>

      <div className="mt-auto pt-5">
        <div className="rounded-control border border-border bg-surface-2 p-3">
          <p className="text-caption text-text-muted">Quota summary</p>
          <dl className="mt-2 space-y-1.5">
            {summary.map((line) => (
              <div key={line.label} className="flex items-baseline justify-between gap-3">
                <dt className="text-meta text-text-secondary">{line.label}</dt>
                <dd className="text-meta text-text-primary text-tabular">{line.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </Card>
  );
}
