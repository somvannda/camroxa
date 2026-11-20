import type { InputHTMLAttributes } from "react";
import { classNames } from "../lib/format";
import type { ControlSize } from "./control-size";

const SIZES: Record<ControlSize, string> = {
  sm: "h-7 text-caption px-2",
  md: "h-[34px] text-body-sm px-3",
  lg: "h-9 text-body px-3",
};

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  controlSize?: ControlSize;
  invalid?: boolean;
}

export function Input({ className, controlSize = "md", invalid = false, ...props }: InputProps) {
  return (
    <input
      className={classNames(
        "w-full rounded-control border bg-[var(--field)] text-text-primary placeholder:text-text-muted focus:outline-none disabled:cursor-not-allowed disabled:opacity-40",
        SIZES[controlSize],
        invalid ? "border-danger focus:border-danger" : "border-border focus:border-accent",
        className,
      )}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
}
