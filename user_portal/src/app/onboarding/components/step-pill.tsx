"use client"

import { Check } from "lucide-react";

export function StepPill(props: { active: boolean; done: boolean; label: string }) {
  return (
    <div
      className={[
        "flex items-center gap-2 rounded-full border px-3 py-1 text-xs",
        props.active
          ? "border-primary/60 bg-primary/10 text-foreground"
          : props.done
            ? "border-border/70 bg-card/60 text-muted-foreground"
            : "border-border/50 bg-background/30 text-muted-foreground",
      ].join(" ")}
    >
      <div
        className={[
          "flex h-4 w-4 items-center justify-center rounded-full border",
          props.done
            ? "border-primary/60 bg-primary/15 text-primary"
            : props.active
              ? "border-primary/50 bg-primary/10 text-primary"
              : "border-border/60 bg-transparent text-muted-foreground",
        ].join(" ")}
      >
        {props.done ? <Check className="h-3 w-3" /> : null}
      </div>
      <div className="whitespace-nowrap">{props.label}</div>
    </div>
  );
}

