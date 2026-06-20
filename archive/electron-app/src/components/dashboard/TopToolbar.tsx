import { TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Square } from "lucide-react";

export function TopToolbar(props: {
  title?: string;
  tabs?: Array<{ value: string; label: string }>;
  variant?: "full" | "titleOnly" | "tabsOnly";
}) {
  const variant = props.variant ?? "full";
  return (
    <div className="border-b border-slate-200/10 bg-slate-950/30 px-3 py-2">
      {variant !== "tabsOnly" ? (
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <Square className="h-4 w-4 text-blue-400" />
            {props.title ?? "Music Generator"}
          </div>
          <div />
        </div>
      ) : null}

      {variant !== "titleOnly" && props.tabs?.length ? (
        <div className={variant === "full" ? "mt-2" : ""}>
          <TabsList className="w-full justify-start">
            {props.tabs.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
      ) : null}
    </div>
  );
}

