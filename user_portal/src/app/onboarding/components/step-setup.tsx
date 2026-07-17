"use client";

import { Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type { OnboardingGenre, PublicDescriptionResponse, WizardState } from "@/app/onboarding/types";

export function StepSetup(props: {
  state: WizardState;
  setSelectedGenre: (genre: OnboardingGenre | null) => void;
  isBusy: boolean;
  onGenerateNames: () => void;
}) {
  const hasGenre = Boolean(props.state.selectedGenre?.name);

  return (
    <div className="grid gap-4">
      <div className="grid gap-2">
        <Label htmlFor="genre">Genre</Label>
        <select
          id="genre"
          className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          disabled={props.state.genresLoading || props.isBusy}
          value={props.state.selectedGenre?.name ?? ""}
          onChange={(event) => {
            const selected = props.state.genres.find((genre) => genre.name === event.target.value);
            props.setSelectedGenre(
              selected
                ? {
                    name: selected.name,
                    matchKey: selected.match_key ?? "",
                  }
                : null,
            );
          }}
        >
          <option value="">
            {props.state.genresLoading ? "Loading genres..." : "Select a genre"}
          </option>
          {props.state.genres.map((genre: PublicDescriptionResponse) => (
            <option key={genre.id} value={genre.name}>
              {genre.name}
            </option>
          ))}
        </select>
      </div>

      <div className="rounded-lg border border-border/60 bg-background/20 p-4 text-sm text-muted-foreground">
        <div>
          <span className="text-foreground">Match key:</span>{" "}
          {props.state.selectedGenre?.matchKey || "Uses genre defaults"}
        </div>
        <div className="mt-2">
          This mirrors the old CAMXORA onboarding draft: one shared genre drives both primary and
          secondary profile generation.
        </div>
      </div>

      <Button onClick={props.onGenerateNames} disabled={!hasGenre || props.isBusy}>
        <Wand2 className="h-4 w-4" />
        Generate primary + secondary names
      </Button>
    </div>
  );
}
