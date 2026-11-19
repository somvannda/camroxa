import type { ButtonHTMLAttributes } from "react";
import { classNames } from "../lib/format";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const variants: Record<Variant, string> = {
  primary: "text-white shadow-[0_8px_24px_rgba(124,58,237,.28)] hover:brightness-110",
  secondary:
    "bg-surface-3 text-text-primary border border-border hover:bg-surface-hover",
  ghost: "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
  danger: "bg-danger text-white hover:brightness-110",
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
        "inline-flex h-9 items-center justify-center gap-1.5 rounded-control px-4 text-body-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40",
        variant === "primary" ? "bg-[image:var(--brand-gradient)]" : "",
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
