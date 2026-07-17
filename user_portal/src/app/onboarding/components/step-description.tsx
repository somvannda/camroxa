"use client";

import { Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export function StepDescription(props: {
  description: string;
  keywordsText: string;
  tagsText: string;
  isBusy: boolean;
  onGenerateDescription: () => void;
  onChangeDescription: (value: string) => void;
  onChangeKeywordsText: (value: string) => void;
  onChangeTagsText: (value: string) => void;
  onClear: () => void;
}) {
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap gap-3">
        <Button onClick={props.onGenerateDescription} disabled={props.isBusy}>
          <Wand2 className="h-4 w-4" />
          Generate shared SEO pack
        </Button>
        <Button variant="outline" onClick={props.onClear} disabled={props.isBusy}>
          Clear
        </Button>
      </div>

      <div className="rounded-lg border border-border/60 bg-background/20 p-4 text-sm text-muted-foreground">
        This is shared across both profiles, matching the old desktop onboarding draft.
      </div>

      <div className="grid gap-2">
        <Label htmlFor="desc">Description</Label>
        <Textarea
          id="desc"
          value={props.description}
          onChange={(e) => props.onChangeDescription(e.target.value)}
          placeholder="Channel description..."
          className="min-h-[140px]"
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="keywords">Keywords (one per line)</Label>
          <Textarea
            id="keywords"
            value={props.keywordsText}
            onChange={(e) => props.onChangeKeywordsText(e.target.value)}
            className="min-h-[140px]"
            placeholder="keyword 1&#10;keyword 2"
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="tags">Tags (one per line)</Label>
          <Textarea
            id="tags"
            value={props.tagsText}
            onChange={(e) => props.onChangeTagsText(e.target.value)}
            className="min-h-[140px]"
            placeholder="tag 1&#10;tag 2"
          />
        </div>
      </div>
    </div>
  );
}
