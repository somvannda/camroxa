import type { InputHTMLAttributes } from "react";
import { classNames } from "../lib/format";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={classNames(
        "h-[34px] w-full rounded-control border border-border bg-[var(--field)] px-3 text-body-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none",
        className,
      )}
      {...props}
    />
  );
}
