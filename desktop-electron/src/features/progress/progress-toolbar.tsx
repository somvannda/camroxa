import { Icon } from "../../components/icon";
import { Button } from "../../components/button";
import { Input } from "../../components/input";
import { classNames } from "../../lib/format";
import {
  LIMIT_OPTIONS,
  STAGE_FILTERS,
  type StageFilter,
} from "./progress-format";

interface ProgressToolbarProps {
  from: string;
  to: string;
  activeOnly: boolean;
  limit: number;
  stage: StageFilter;
  busy: boolean;
  rangeMessage: string | null;
  lastLoadedAt: number | null;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
  onActiveOnlyChange: (value: boolean) => void;
  onLimitChange: (value: number) => void;
  onStageChange: (value: StageFilter) => void;
  onRefresh: () => void;
}

const selectClass =
  "h-8 rounded-control border border-border bg-surface-1 px-2 text-body text-text-primary focus:border-accent focus:outline-none disabled:opacity-40";

function lastUpdatedLabel(value: number | null): string | null {
  if (!value) return null;
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

export function ProgressToolbar({
  from,
  to,
  activeOnly,
  limit,
  stage,
  busy,
  rangeMessage,
  lastLoadedAt,
  onFromChange,
  onToChange,
  onActiveOnlyChange,
  onLimitChange,
  onStageChange,
  onRefresh,
}: ProgressToolbarProps) {
  const updated = lastUpdatedLabel(lastLoadedAt);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
        <label className="flex flex-col gap-1">
          <span className="text-caption text-text-muted">From</span>
          <Input
            type="date"
            className="w-[144px]"
            value={from}
            max={to || undefined}
            onChange={(event) => onFromChange(event.target.value)}
            data-testid="progress-from"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-caption text-text-muted">To</span>
          <Input
            type="date"
            className="w-[144px]"
            value={to}
            min={from || undefined}
            onChange={(event) => onToChange(event.target.value)}
            data-testid="progress-to"
          />
        </label>
        <label className="flex h-8 shrink-0 items-center gap-2 text-body text-text-secondary">
          <input
            type="checkbox"
            className="h-4 w-4 rounded-[4px] border border-border-strong bg-surface-1 accent-accent"
            checked={activeOnly}
            onChange={(event) => onActiveOnlyChange(event.target.checked)}
            data-testid="progress-active"
          />
          Active only
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-caption text-text-muted">Limit</span>
          <select
            className={classNames(selectClass, "w-[88px]")}
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
            data-testid="progress-limit"
          >
            {LIMIT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-caption text-text-muted">Stage</span>
          <select
            className={classNames(selectClass, "w-[132px]")}
            value={stage}
            onChange={(event) => onStageChange(event.target.value as StageFilter)}
            data-testid="progress-stage"
          >
            {STAGE_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <Button
          variant="secondary"
          onClick={onRefresh}
          disabled={busy || Boolean(rangeMessage)}
          data-testid="progress-refresh"
        >
          <Icon name="fa-rotate" size={14} />
          {busy ? "Refreshing" : "Refresh"}
        </Button>
        {updated ? (
          <span className="ml-auto pb-1.5 font-mono text-caption text-text-muted">
            Updated {updated}
          </span>
        ) : null}
      </div>
      {rangeMessage ? (
        <p className="text-meta text-danger" role="alert" data-testid="progress-range-error">
          {rangeMessage}
        </p>
      ) : null}
    </div>
  );
}
