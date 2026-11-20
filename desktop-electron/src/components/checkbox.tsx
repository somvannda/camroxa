import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import type { ReactNode } from "react";
import { Icon } from "./icon";
import { classNames } from "../lib/format";

export interface CheckboxProps {
  id?: string;
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  required?: boolean;
  name?: string;
  label?: ReactNode;
  hint?: ReactNode;
  className?: string;
  "data-testid"?: string;
  "aria-label"?: string;
}

/** Radix checkbox with the shared 16px box and accent check. */
export function Checkbox({
  id,
  checked,
  onCheckedChange,
  disabled,
  required,
  name,
  label,
  hint,
  className,
  "data-testid": testId,
  "aria-label": ariaLabel,
}: CheckboxProps) {
  return (
    <div className={classNames("flex items-start gap-2", className)}>
      <CheckboxPrimitive.Root
        id={id}
        data-testid={testId}
        aria-label={ariaLabel}
        checked={checked}
        onCheckedChange={(next) => onCheckedChange?.(next === true)}
        disabled={disabled}
        required={required}
        name={name}
        className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border border-border-strong bg-surface-1 transition-colors data-[state=checked]:border-accent data-[state=checked]:bg-accent disabled:cursor-not-allowed disabled:opacity-40"
      >
        <CheckboxPrimitive.Indicator className="text-white">
          <Icon name="fa-check" size={9} />
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
      {label ? (
        <button
          type="button"
          className={classNames(
            "min-w-0 text-left text-body",
            disabled ? "cursor-not-allowed text-text-disabled" : "cursor-pointer",
          )}
          disabled={disabled}
          onClick={() => onCheckedChange?.(!checked)}
          tabIndex={-1}
        >
          <span
            className={classNames(
              "whitespace-nowrap",
              disabled ? "text-text-disabled" : "text-text-primary",
            )}
          >
            {label}
          </span>
          {hint ? <span className="mt-0.5 block text-caption text-text-muted">{hint}</span> : null}
        </button>
      ) : null}
    </div>
  );
}
