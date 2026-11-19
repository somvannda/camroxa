import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { useId } from "react";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Dialog, DialogContent } from "../../components/dialog";
import { Icon } from "../../components/icon";
import { Input } from "../../components/input";
import { classNames } from "../../lib/format";

/** Shared Settings form primitives. Tokens only; no page-specific styling. */

export function Section({
  title,
  description,
  action,
  children,
  className,
  "data-testid": testId,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  "data-testid"?: string;
}) {
  return (
    <Card className={classNames("p-4", className)} data-testid={testId}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-title font-semibold text-text-primary">{title}</h2>
          {description ? <p className="mt-1 text-body text-text-secondary">{description}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="mt-4 space-y-4">{children}</div>
    </Card>
  );
}

export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label className="mb-1.5 block text-meta text-text-secondary" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error ? (
        <p className="mt-1 text-caption text-danger" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1 text-caption text-text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

export function TextInput({
  id,
  label,
  hint,
  error,
  mono,
  ...props
}: {
  id?: string;
  label: string;
  hint?: string;
  error?: string;
  mono?: boolean;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "className">) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <Field label={label} htmlFor={fieldId} hint={hint} error={error}>
      <Input
        id={fieldId}
        className={classNames(
          error ? "border-danger" : undefined,
          mono ? "font-mono text-meta" : undefined,
        )}
        aria-invalid={error ? true : undefined}
        {...props}
      />
    </Field>
  );
}

export function TextAreaInput({
  id,
  label,
  hint,
  error,
  rows = 3,
  ...props
}: {
  id?: string;
  label: string;
  hint?: string;
  error?: string;
  rows?: number;
} & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className">) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <Field label={label} htmlFor={fieldId} hint={hint} error={error}>
      <textarea
        id={fieldId}
        rows={rows}
        className={classNames(
          "w-full resize-y rounded-control border border-border bg-surface-1 px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-50",
          error ? "border-danger" : undefined,
        )}
        aria-invalid={error ? true : undefined}
        {...props}
      />
    </Field>
  );
}

export function SelectInput({
  id,
  label,
  hint,
  error,
  options,
  placeholder,
  ...props
}: {
  id?: string;
  label: string;
  hint?: string;
  error?: string;
  options: Array<{ value: string; label: string; disabled?: boolean }>;
  placeholder?: string;
} & Omit<SelectHTMLAttributes<HTMLSelectElement>, "className" | "children">) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <Field label={label} htmlFor={fieldId} hint={hint} error={error}>
      <select
        id={fieldId}
        className={classNames(
          "h-8 w-full rounded-control border border-border bg-surface-1 px-2.5 text-body text-text-primary focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-50",
          error ? "border-danger" : undefined,
        )}
        aria-invalid={error ? true : undefined}
        {...props}
      >
        {placeholder ? (
          <option value="">{placeholder}</option>
        ) : null}
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function NumberInput({
  id,
  label,
  hint,
  error,
  min,
  max,
  ...props
}: {
  id?: string;
  label: string;
  hint?: string;
  error?: string;
  min: number;
  max: number;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "min" | "max" | "type">) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <Field label={label} htmlFor={fieldId} hint={hint} error={error}>
      <Input
        id={fieldId}
        type="number"
        min={min}
        max={max}
        className={classNames("text-tabular", error ? "border-danger" : undefined)}
        aria-invalid={error ? true : undefined}
        {...props}
      />
    </Field>
  );
}

export function CheckboxInput({
  id,
  label,
  hint,
  ...props
}: {
  id?: string;
  label: string;
  hint?: string;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "type">) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <div>
      <label className="flex cursor-pointer items-center gap-2 text-body text-text-primary" htmlFor={fieldId}>
        <input
          id={fieldId}
          type="checkbox"
          className="h-4 w-4 rounded border-border bg-surface-1 accent-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50"
          {...props}
        />
        {label}
      </label>
      {hint ? <p className="mt-1 pl-6 text-caption text-text-muted">{hint}</p> : null}
    </div>
  );
}

export function Note({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "warning" }) {
  return (
    <p
      className={classNames(
        "rounded-control border px-3 py-2 text-meta",
        tone === "warning"
          ? "border-warning/30 bg-warning-soft text-warning"
          : "border-border bg-surface-2 text-text-secondary",
      )}
    >
      {children}
    </p>
  );
}

export function ErrorBanner({
  message,
  onRetry,
  retryLabel = "Retry",
}: {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <div
      className="flex items-start justify-between gap-3 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-body text-danger"
      role="alert"
    >
      <span className="flex items-start gap-2">
        <Icon name="fa-triangle-exclamation" size={15} className="mt-0.5 shrink-0" />
        <span>{message}</span>
      </span>
      {onRetry ? (
        <Button variant="ghost" className="h-7 shrink-0 px-2 text-danger" onClick={onRetry}>
          <Icon name="fa-rotate-right" size={13} />
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}

export function InlineWarning({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-2 rounded-control border border-warning/30 bg-warning-soft px-3 py-2 text-meta text-warning">
      <Icon name="fa-triangle-exclamation" size={14} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="rounded-card border border-border bg-surface-1 px-4 py-8 text-center">
      <p className="text-body text-text-secondary">{message}</p>
      {action ? <div className="mt-3 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function Skeleton({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={classNames("space-y-3", className)} aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="space-y-2">
          <div className="h-2.5 w-24 rounded bg-surface-2" />
          <div className="h-8 w-full rounded-control bg-surface-2" />
        </div>
      ))}
    </div>
  );
}

export function KeyValueRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2 last:border-b-0">
      <span className="text-meta text-text-muted">{label}</span>
      <span className="min-w-0 truncate text-body text-text-primary text-tabular">{value}</span>
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  description,
  body,
  confirmLabel,
  tone = "primary",
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  body?: ReactNode;
  confirmLabel: string;
  tone?: "primary" | "danger";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onCancel())}>
      <DialogContent title={title} description={description} className="max-w-[520px]">
        {body ? <div className="text-body text-text-secondary">{body}</div> : null}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            loading={busy}
            disabled={busy}
          >
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
