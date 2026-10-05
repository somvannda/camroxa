import type { HTMLAttributes, ReactNode } from "react";

/** Frosted panel used for every card in the console. */
export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`glass rounded-xl ${className}`} {...props} />;
}

export function StatCard({
  label,
  value,
  hint,
  className = "",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`glass rounded-xl p-5 ${className}`}>
      <div className="text-sm text-[var(--muted)]">{label}</div>
      <div className="grad-text mt-1 text-3xl font-bold">{value}</div>
      {hint && <div className="mt-1 text-xs text-[var(--muted)]">{hint}</div>}
    </div>
  );
}
