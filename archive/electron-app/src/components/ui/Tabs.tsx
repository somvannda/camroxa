import * as React from "react";
import { cn } from "@/lib/utils";

type Ctx = {
  value: string;
  setValue: (v: string) => void;
};

const TabsContext = React.createContext<Ctx | null>(null);

export function Tabs({ value, onValueChange, children }: { value: string; onValueChange: (v: string) => void; children: React.ReactNode }) {
  const ctx = React.useMemo(() => ({ value, setValue: onValueChange }), [value, onValueChange]);
  return <TabsContext.Provider value={ctx}>{children}</TabsContext.Provider>;
}

export function TabsList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 rounded-lg border border-slate-200/10 bg-slate-950/40 p-1",
        className,
      )}
      {...props}
    />
  );
}

export function TabsTrigger({ value, className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string }) {
  const ctx = React.useContext(TabsContext);
  const active = ctx?.value === value;
  return (
    <button
      type="button"
      onClick={() => ctx?.setValue(value)}
      className={cn(
        "h-8 rounded-md px-3 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/60",
        active ? "bg-blue-600 text-white" : "text-slate-200 hover:bg-slate-800/60",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({ value, className, ...props }: React.HTMLAttributes<HTMLDivElement> & { value: string }) {
  const ctx = React.useContext(TabsContext);
  if (!ctx || ctx.value !== value) return null;
  return <div className={cn("mt-3", className)} {...props} />;
}

