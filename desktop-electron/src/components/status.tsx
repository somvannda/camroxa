import type { ReactNode } from "react";
import { classNames } from "../lib/format";

type Tone = "neutral" | "success" | "warning" | "danger" | "accent";

const dot: Record<Tone, string> = {
  neutral: "bg-text-muted",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  accent: "bg-accent",
};

export function StatusDot({ tone = "neutral", label }: { tone?: Tone; label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-meta text-text-secondary">
      <span className={classNames("h-1.5 w-1.5 rounded-full", dot[tone])} />
      {label}
    </span>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  const tones: Record<Tone, string> = {
    neutral: "border-border bg-surface-2 text-text-secondary",
    success: "border-success/30 bg-success-soft text-success",
    warning: "border-warning/30 bg-warning-soft text-warning",
    danger: "border-danger/30 bg-danger-soft text-danger",
    accent: "border-accent-line bg-accent-soft text-accent",
  };
  return (
    <span className={classNames("inline-flex h-5 items-center rounded-full border px-2 text-caption", tones[tone])}>
      {children}
    </span>
  );
}
