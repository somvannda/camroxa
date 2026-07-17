"use client";

import { Check } from "lucide-react";

import { Label } from "@/components/ui/label";

function SuggestionsCard(props: {
  title: string;
  suggestions: string[];
  selectedName: string;
  onSelect: (name: string) => void;
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-background/20 p-4">
      <Label className="text-sm font-medium">{props.title}</Label>
      <div className="mt-3 grid gap-2">
        {props.suggestions.length === 0 ? (
          <div className="text-sm text-muted-foreground">No names yet. Generate suggestions first.</div>
        ) : (
          props.suggestions.map((name) => (
            <button
              key={`${props.title}-${name}`}
              type="button"
              onClick={() => props.onSelect(name)}
              className={[
                "flex items-center justify-between rounded-md border px-3 py-2 text-left transition-colors",
                name === props.selectedName
                  ? "border-primary/60 bg-primary/10"
                  : "border-border/60 bg-background/30 hover:bg-accent/30",
              ].join(" ")}
            >
              <div className="truncate font-medium">{name}</div>
              {name === props.selectedName ? <Check className="h-4 w-4 text-primary" /> : null}
            </button>
          ))
        )}
      </div>
    </div>
  );
}

export function StepNames(props: {
  primarySuggestions: string[];
  secondarySuggestions: string[];
  primaryName: string;
  secondaryName: string;
  setPrimaryName: (name: string) => void;
  setSecondaryName: (name: string) => void;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <SuggestionsCard
        title="Primary profile"
        suggestions={props.primarySuggestions}
        selectedName={props.primaryName}
        onSelect={props.setPrimaryName}
      />
      <SuggestionsCard
        title="Secondary profile"
        suggestions={props.secondarySuggestions}
        selectedName={props.secondaryName}
        onSelect={props.setSecondaryName}
      />
    </div>
  );
}
