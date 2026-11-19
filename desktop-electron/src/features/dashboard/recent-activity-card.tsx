import { Card } from "../../components/card";
import { Badge } from "../../components/status";
import { Table, TBody, TD, TH, THead, TR } from "../../components/table";
import { activityTone, type ActivityRow, type PlanBadge } from "./dashboard-format";

const COLUMNS = ["Time", "Type", "Batch", "Channel", "Stage", "Detail"];
const COLUMN_COUNT = COLUMNS.length;

interface RecentActivityCardProps {
  rows: ActivityRow[];
  plan: PlanBadge;
  loading: boolean;
}

export function RecentActivityCard({ rows, plan, loading }: RecentActivityCardProps) {
  return (
    <Card className="p-5" data-testid="recent-activity">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-title font-semibold text-text-primary">Recent Activity</h2>
          <p className="mt-1 text-body text-text-secondary">
            Latest events returned by the dashboard stats API.
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-body font-medium text-text-primary">{plan.plan}</p>
          <p className="text-caption text-text-secondary">{plan.expiryLine}</p>
        </div>
      </div>

      <div className="mt-4">
        <Table>
          <THead>
            <TR className="hover:bg-surface-2">
              {COLUMNS.map((column) => (
                <TH key={column}>{column}</TH>
              ))}
            </TR>
          </THead>
          <TBody>
            {loading ? (
              <TR className="hover:bg-transparent">
                <TD colSpan={COLUMN_COUNT} className="text-text-secondary">
                  Loading recent activity...
                </TD>
              </TR>
            ) : rows.length === 0 ? (
              <TR className="hover:bg-transparent">
                <TD colSpan={COLUMN_COUNT} className="text-text-secondary">
                  No recent activity found.
                </TD>
              </TR>
            ) : (
              rows.map((row) => (
                <TR key={row.key}>
                  <TD className="text-text-secondary text-tabular">{row.time}</TD>
                  <TD>{row.type}</TD>
                  <TD className="text-text-muted">{row.batch}</TD>
                  <TD className="text-text-muted">{row.channel}</TD>
                  <TD>
                    <Badge tone={activityTone(row.stage)}>{row.stage}</Badge>
                  </TD>
                  <TD className="max-w-[420px] truncate text-text-secondary" title={row.detail}>
                    {row.detail}
                  </TD>
                </TR>
              ))
            )}
          </TBody>
        </Table>
      </div>
    </Card>
  );
}
