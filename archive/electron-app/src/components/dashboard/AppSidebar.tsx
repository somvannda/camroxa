import { cn } from "@/lib/utils";

export type AppSection = "music" | "image" | "video" | "merger" | "settings";

export function AppSidebar(props: {
  section: AppSection;
  onSectionChange: (v: AppSection) => void;
}) {
  const items: Array<{ key: AppSection; label: string }> = [
    { key: "music", label: "Music" },
    { key: "image", label: "Image" },
    { key: "video", label: "Video" },
    { key: "merger", label: "Merger" },
    { key: "settings", label: "Settings" },
  ];

  return (
    <div className="flex h-full w-56 shrink-0 flex-col border-r border-slate-200/10 bg-slate-950/30 p-2">
      <div className="space-y-1">
        {items.map((it) => (
          <button
            key={it.key}
            type="button"
            onClick={() => props.onSectionChange(it.key)}
            className={cn(
              "w-full rounded-md px-3 py-2 text-left text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/60",
              props.section === it.key ? "bg-blue-600 text-white" : "text-slate-200 hover:bg-slate-800/60",
            )}
          >
            {it.label}
          </button>
        ))}
      </div>
    </div>
  );
}
