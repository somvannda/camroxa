"use client";

import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";

function ReviewCard(props: {
  title: string;
  name: string;
  hasLogo: boolean;
  hasCover: boolean;
  isCreated: boolean;
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-background/30 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium">{props.title}</div>
        <div className="text-xs text-muted-foreground">{props.isCreated ? "Created" : "Pending"}</div>
      </div>
      <div className="mt-3 grid gap-2 text-sm text-muted-foreground">
        <div>
          <span className="text-foreground">Name:</span> {props.name || "—"}
        </div>
        <div>
          <span className="text-foreground">Logo:</span> {props.hasLogo ? "Ready" : "None"}
        </div>
        <div>
          <span className="text-foreground">Cover:</span> {props.hasCover ? "Ready" : "None"}
        </div>
      </div>
    </div>
  );
}

export function StepReview(props: {
  genreName: string;
  matchKey: string;
  primaryName: string;
  secondaryName: string;
  primaryLogoBase64: string | null;
  secondaryLogoBase64: string | null;
  primaryCoverBase64: string | null;
  secondaryCoverBase64: string | null;
  description: string;
  keywords: string[];
  tags: string[];
  hasExistingPrimary: boolean;
  hasExistingSecondary: boolean;
  isBusy: boolean;
  onCreateProfiles: () => void;
}) {
  const canCreate =
    props.primaryName.trim().length > 0 &&
    props.secondaryName.trim().length > 0 &&
    props.genreName.trim().length > 0;

  return (
    <div className="grid gap-4">
      <div className="grid gap-4 md:grid-cols-2">
        <ReviewCard
          title="Primary profile"
          name={props.primaryName}
          hasLogo={Boolean(props.primaryLogoBase64)}
          hasCover={Boolean(props.primaryCoverBase64)}
          isCreated={props.hasExistingPrimary}
        />
        <ReviewCard
          title="Secondary profile"
          name={props.secondaryName}
          hasLogo={Boolean(props.secondaryLogoBase64)}
          hasCover={Boolean(props.secondaryCoverBase64)}
          isCreated={props.hasExistingSecondary}
        />
      </div>

      <div className="rounded-lg border border-border/60 bg-background/20 p-4 text-sm text-muted-foreground">
        <div>
          <span className="text-foreground">Genre:</span> {props.genreName || "—"}
        </div>
        <div className="mt-2">
          <span className="text-foreground">Match key:</span> {props.matchKey || "—"}
        </div>
        <div className="mt-2">
          <span className="text-foreground">Shared description:</span>{" "}
          {props.description.trim() ? "Ready" : "Optional"}
        </div>
        <div className="mt-2">
          <span className="text-foreground">Keywords:</span> {props.keywords.length}
        </div>
        <div className="mt-2">
          <span className="text-foreground">Tags:</span> {props.tags.length}
        </div>
      </div>

      <Button onClick={props.onCreateProfiles} disabled={!canCreate || props.isBusy} className="w-full">
        <Sparkles className="h-4 w-4" />
        Complete onboarding
      </Button>
    </div>
  );
}
