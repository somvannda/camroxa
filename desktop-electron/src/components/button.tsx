import type { ButtonHTMLAttributes } from "react";
import { classNames } from "../lib/format";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const variants: Record<Variant, string> = {
  primary: "bg-text-primary text-bg hover:bg-white",
  secondary:
    "bg-surface-2 text-text-primary border border-border-strong hover:bg-surface-hover",
  ghost: "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
  danger: "bg-danger text-bg hover:brightness-110",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

export function Button({
  variant = "secondary",
  loading = false,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={classNames(
        "inline-flex h-8 items-center justify-center gap-2 rounded-control px-3 text-body font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40",
        variants[variant],
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" /> : null}
      {children}
    </button>
  );
}
