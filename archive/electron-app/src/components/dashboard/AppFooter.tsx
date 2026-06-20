import * as React from "react";
import { cn } from "@/lib/utils";

export function AppFooter(props: { text: string; progress: number | null; sunoText?: string }) {
  const [size, setSize] = React.useState<{ w: number; h: number }>(() => ({ w: window.innerWidth, h: window.innerHeight }));

  React.useEffect(() => {
    function onResize() {
      setSize({ w: window.innerWidth, h: window.innerHeight });
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <div className="h-7 border-t border-slate-200/10 bg-slate-950/40 px-3">
      <div className="flex h-full items-center gap-3">
        <div className="min-w-0 flex-1 truncate text-xs text-slate-200">
          {props.text}
          {props.sunoText ? <span className="text-slate-400"> · {props.sunoText}</span> : null}
        </div>
        <div className="w-10 text-right text-[11px] tabular-nums text-slate-400">{props.progress === null ? "" : `${Math.round(props.progress)}%`}</div>
        <div className="w-48">
          <div className={cn("h-1.5 w-full rounded-full bg-slate-800/70", props.progress === null ? "opacity-40" : "")}
            aria-hidden
          >
            <div
              className={cn("h-1.5 rounded-full bg-blue-500", props.progress === null ? "w-0" : "")}
              style={{ width: `${props.progress === null ? 0 : Math.max(0, Math.min(100, props.progress))}%` }}
            />
          </div>
        </div>
        <div className="text-[11px] text-slate-400" title={`Window size: ${size.w}×${size.h}`}>
          {size.w}×{size.h}
        </div>
      </div>
    </div>
  );
}
