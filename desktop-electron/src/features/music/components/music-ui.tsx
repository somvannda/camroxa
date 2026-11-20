import { Checkbox } from "../../../components/checkbox";
import { Field, FieldLabel } from "../../../components/field";
import { Input } from "../../../components/input";
import { Range } from "../../../components/range";
import { Select } from "../../../components/select";
import { classNames } from "../../../lib/format";

export { FieldLabel };

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
    <Field id={id} label={label} className={className}>
      <Select
        id={id}
        data-testid={testId}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
    </Field>
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
    <Field id={id} label={label} className={className}>
      <Input
        id={id}
        data-testid={testId}
        type="number"
        controlSize="md"
        className="text-tabular"
        value={value}
        min={min}
        max={max}
        disabled={disabled}
        onChange={(event) => {
          const parsed = Number.parseInt(event.target.value, 10);
          if (Number.isFinite(parsed)) onChange(parsed);
        }}
      />
    </Field>
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
    <Field id={id} label={label}>
      <Input
        id={id}
        data-testid={testId}
        type="date"
        controlSize="md"
        className="text-tabular"
        value={value}
        invalid={invalid}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
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
      <Range
        id={id}
        data-testid={testId}
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
    <Checkbox
      id={id}
      data-testid={testId}
      label={label}
      hint={hint}
      checked={checked}
      disabled={disabled}
      onChange={(event) => onChange(event.target.checked)}
    />
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
