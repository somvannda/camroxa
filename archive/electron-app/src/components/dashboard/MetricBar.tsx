import { cn } from "@/lib/utils";

export function MetricBar({
  label,
  value,
  tone,
  className,
}: {
  label: string;
  value: number;
  tone: "blue" | "amber";
  className?: string;
}) {
  const bar = tone === "blue" ? "bg-blue-500" : "bg-amber-500";
  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex min-w-0 items-center justify-between gap-2 text-xs text-slate-200">
        <span className="min-w-0 truncate">{label}</span>
        <span className="shrink-0 tabular-nums text-slate-300">{Math.round(value)}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-800/70">
        <div className={cn("h-2 rounded-full", bar)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}

