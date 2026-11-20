import type { InputHTMLAttributes, ReactNode } from "react";
import { classNames } from "../lib/format";

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: ReactNode;
  hint?: ReactNode;
}

/**
 * Shared checkbox. Native input keeps Playwright and keyboard behaviour intact;
 * the wrapper owns spacing and label/hint typography.
 */
export function Checkbox({ label, hint, className, disabled, id, ...props }: CheckboxProps) {
  return (
    <label
      htmlFor={id}
      className={classNames(
        "flex items-start gap-2 text-body",
        disabled ? "text-text-disabled" : "cursor-pointer text-text-secondary",
        className,
      )}
    >
      <input
        id={id}
        type="checkbox"
        disabled={disabled}
        className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-accent disabled:cursor-not-allowed disabled:opacity-40"
        {...props}
      />
      {label ? (
        <span className="min-w-0">
          <span
            className={classNames(
              "whitespace-nowrap",
              disabled ? "text-text-disabled" : "text-text-primary",
            )}
          >
            {label}
          </span>
          {hint ? <span className="mt-0.5 block text-caption text-text-muted">{hint}</span> : null}
        </span>
      ) : null}
    </label>
  );
}
