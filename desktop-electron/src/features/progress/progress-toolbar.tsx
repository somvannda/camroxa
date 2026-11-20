import { Icon } from "../../components/icon";
import { Button } from "../../components/button";
import { Checkbox } from "../../components/checkbox";
import { DatePicker } from "../../components/date-picker";
import { Field } from "../../components/field";
import { Select } from "../../components/select";
import { LIMIT_OPTIONS, STAGE_FILTERS, type StageFilter } from "./progress-format";

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
        <Field label="From" className="w-[190px]">
          <DatePicker
            id="progress-from"
            value={from}
            max={to || undefined}
            onChange={onFromChange}
            data-testid="progress-from"
          />
        </Field>
        <Field label="To" className="w-[190px]">
          <DatePicker
            id="progress-to"
            value={to}
            min={from || undefined}
            onChange={onToChange}
            data-testid="progress-to"
          />
        </Field>
        <div className="flex h-8 shrink-0 items-center">
          <Checkbox
            label="Active only"
            checked={activeOnly}
            onCheckedChange={onActiveOnlyChange}
            data-testid="progress-active"
          />
        </div>
        <Field label="Limit" className="w-[88px]">
          <Select
            value={limit}
            options={LIMIT_OPTIONS.map((option) => ({ value: option, label: String(option) }))}
            onValueChange={(next) => onLimitChange(Number(next))}
            data-testid="progress-limit"
          />
        </Field>
        <Field label="Stage" className="w-[132px]">
          <Select
            value={stage}
            options={STAGE_FILTERS.map((option) => ({
              value: option.value,
              label: option.label,
            }))}
            onValueChange={(next) => onStageChange(next as StageFilter)}
            data-testid="progress-stage"
          />
        </Field>
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
