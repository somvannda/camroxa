import * as React from "react";
import { cn } from "@/lib/utils";

export function Select({ className, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-9 rounded-md border border-slate-200/10 bg-slate-950/40 px-3 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500/60",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

