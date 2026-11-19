import type { ChangeEvent, ReactNode } from "react";
import { classNames } from "../../../lib/format";

export const controlClass =
  "h-8 w-full rounded-control border border-border bg-surface-1 px-2 text-body text-text-primary focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-40";

export function FieldLabel({
  children,
  htmlFor,
  className,
}: {
  children: ReactNode;
  htmlFor?: string;
  className?: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className={classNames("block text-meta text-text-muted", className)}
    >
      {children}
    </label>
  );
}

export function SelectField({
  id,
  label,
  value,
  options,
  onChange,
  disabled,
  className,
  testId,
}: {
  id: string;
  label: string;
  value: string | number;
  options: Array<{ value: string | number; label: string }>;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
  testId?: string;
}) {
  return (
    <div className={classNames("min-w-0", className)}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <select
        id={id}
        data-testid={testId}
        className={classNames(controlClass, "mt-1")}
        value={value}
        disabled={disabled}
        onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export function NumberField({
  id,
  label,
  value,
  min,
  max,
  onChange,
  disabled,
  testId,
  className,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  testId?: string;
  className?: string;
}) {
  return (
    <div className={classNames("min-w-0", className)}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <input
        id={id}
        data-testid={testId}
        type="number"
        className={classNames(controlClass, "mt-1 text-tabular")}
        value={value}
        min={min}
        max={max}
        disabled={disabled}
        onChange={(event) => {
          const parsed = Number.parseInt(event.target.value, 10);
          if (Number.isFinite(parsed)) onChange(parsed);
        }}
      />
    </div>
  );
}

export function DateField({
  id,
  label,
  value,
  onChange,
  invalid,
  testId,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
  testId?: string;
}) {
  return (
    <div className="min-w-0">
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <input
        id={id}
        data-testid={testId}
        type="date"
        className={classNames(
          controlClass,
          "mt-1 text-tabular",
          invalid && "border-danger focus:border-danger",
        )}
        value={value}
        aria-invalid={invalid ? true : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

export function RangeField({
  id,
  label,
  value,
  min = 0,
  max = 100,
  onChange,
  testId,
  className,
  disabled,
}: {
  id: string;
  label: string;
  value: number;
  min?: number;
  max?: number;
  onChange: (value: number) => void;
  testId?: string;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <div className={classNames("min-w-0", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <FieldLabel htmlFor={id}>{label}</FieldLabel>
        <span className="text-meta text-text-secondary text-tabular">{value}</span>
      </div>
      <input
        id={id}
        data-testid={testId}
        type="range"
        className="mt-2 w-full accent-accent disabled:opacity-40"
        value={value}
        min={min}
        max={max}
        disabled={disabled}
        onChange={(event) => onChange(Number.parseInt(event.target.value, 10))}
      />
    </div>
  );
}

export function CheckField({
  id,
  label,
  checked,
  onChange,
  disabled,
  hint,
  testId,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  hint?: string;
  testId?: string;
}) {
  return (
    <label
      htmlFor={id}
      className={classNames(
        "flex items-start gap-2 text-body",
        disabled ? "text-text-disabled" : "cursor-pointer text-text-secondary",
      )}
    >
      <input
        id={id}
        data-testid={testId}
        type="checkbox"
        className="mt-0.5 h-4 w-4 shrink-0 accent-accent disabled:opacity-40"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="min-w-0">
        <span className={classNames("whitespace-nowrap", disabled ? "text-text-disabled" : "text-text-primary")}>{label}</span>
        {hint ? <span className="mt-0.5 block text-caption text-text-muted">{hint}</span> : null}
      </span>
    </label>
  );
}

export function Meter({ label, value, testId }: { label: string; value: number; testId?: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-meta text-text-muted">{label}</span>
        <span className="text-meta text-text-secondary text-tabular" data-testid={testId}>
          {value}
        </span>
      </div>
      <div
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-3"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
      >
        <div className="h-full rounded-full bg-accent" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}
