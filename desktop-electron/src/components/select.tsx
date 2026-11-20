import type { SelectHTMLAttributes } from "react";
import { Icon } from "./icon";
import { classNames } from "../lib/format";

export type ControlSize = "sm" | "md" | "lg";

const SIZES: Record<ControlSize, string> = {
  sm: "h-7 text-caption",
  md: "h-8 text-body",
  lg: "h-9 text-body",
};

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  controlSize?: ControlSize;
  invalid?: boolean;
  /** Wrapper class; the select itself always fills the wrapper. */
  wrapperClassName?: string;
}

/** Shared select: native keyboard/menu behaviour with one visual language. */
export function Select({
  controlSize = "md",
  invalid = false,
  className,
  wrapperClassName,
  children,
  ...props
}: SelectProps) {
  return (
    <div className={classNames("relative block w-full", wrapperClassName)}>
      <select
        className={classNames(
          "w-full appearance-none rounded-control border bg-surface-1 pl-2 pr-7 text-text-primary focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-40",
          SIZES[controlSize],
          invalid ? "border-danger focus:border-danger" : "border-border",
          className,
        )}
        aria-invalid={invalid || undefined}
        {...props}
      >
        {children}
      </select>
      <Icon
        name="fa-chevron-down"
        size={9}
        className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-text-muted"
      />
    </div>
  );
}
