"use client";

import Image from "next/image";
import { Check, Image as ImageIcon, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";

export function StepCovers(props: {
  coverBase64: string | null;
  coverOptions: string[];
  isBusy: boolean;
  onGenerateCovers: () => void;
  onSelectCover: (base64: string) => void;
  onClearCover: () => void;
}) {
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap gap-3">
        <Button onClick={props.onGenerateCovers} disabled={props.isBusy}>
          <Wand2 className="h-4 w-4" />
          Generate covers
        </Button>
        <Button variant="outline" onClick={props.onClearCover} disabled={props.isBusy}>
          Clear
        </Button>
      </div>

      {props.coverOptions.length > 0 ? (
        <div className="grid gap-3 md:grid-cols-2">
          {props.coverOptions.map((b64, idx) => {
            const selected = props.coverBase64 === b64;
            return (
              <button
                key={`${idx}-${b64.slice(0, 16)}`}
                type="button"
                onClick={() => props.onSelectCover(b64)}
                className={[
                  "group relative overflow-hidden rounded-lg border text-left transition-colors",
                  selected
                    ? "border-primary/60 bg-primary/10"
                    : "border-border/60 bg-background/30 hover:bg-accent/30",
                ].join(" ")}
              >
                <div className="relative aspect-[16/9] w-full">
                  <Image
                    alt={`Cover ${idx + 1}`}
                    src={`data:image/png;base64,${b64}`}
                    fill
                    sizes="(min-width: 768px) 520px, 100vw"
                    className="object-cover"
                  />
                </div>
                <div className="flex items-center justify-between gap-3 px-3 py-2">
                  <div className="text-sm font-medium">Cover {idx + 1}</div>
                  {selected ? <Check className="h-4 w-4 text-primary" /> : null}
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-lg border border-dashed border-border/60 bg-background/20 p-6 text-sm text-muted-foreground">
          <ImageIcon className="h-4 w-4" />
          No covers yet. Generate banner options and choose one persisted cover.
        </div>
      )}
    </div>
  );
}
