import type { ReactNode } from "react";
import { classNames } from "../lib/format";

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
    <label htmlFor={htmlFor} className={classNames("block text-meta text-text-muted", className)}>
      {children}
    </label>
  );
}

export function Field({
  id,
  label,
  hint,
  error,
  className,
  children,
}: {
  id?: string;
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={classNames("min-w-0", className)}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <div className="mt-1">{children}</div>
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
