import { Button } from "../../../components/button";
import { Card } from "../../../components/card";
import { Input } from "../../../components/input";
import { LYRIC_LIMIT, type MusicSettings } from "../music-settings";
import type { EffectPreview } from "../music-format";
import type { ComposerState } from "../music-types";
import { FieldLabel, Meter, RangeField } from "./music-ui";

interface SongEditorCardProps {
  composer: ComposerState;
  settings: MusicSettings;
  effects: EffectPreview;
  draftLabel: string;
  polishLabel: string;
  drafting: boolean;
  polishing: boolean;
  draftEnabled: boolean;
  polishEnabled: boolean;
  seedNotice: string;
  undoAvailable: boolean;
  onDraft: () => void;
  onPolish: () => void;
  onUndo: () => void;
  onFieldChange: (patch: Partial<ComposerState>) => void;
  onPolishStrength: (value: number) => void;
  onCopy: (kind: "title" | "lyrics" | "both") => void;
}

export function SongEditorCard({
  composer,
  settings,
  effects,
  draftLabel,
  polishLabel,
  drafting,
  polishing,
  draftEnabled,
  polishEnabled,
  seedNotice,
  undoAvailable,
  onDraft,
  onPolish,
  onUndo,
  onFieldChange,
  onPolishStrength,
  onCopy,
}: SongEditorCardProps) {
  const lyricLength = composer.lyrics.length;
  const overLimit = lyricLength > LYRIC_LIMIT;
  const hasTitle = composer.title.trim().length > 0;
  const hasLyrics = composer.lyrics.trim().length > 0;

  return (
    <Card className="flex min-h-0 min-w-0 flex-col p-4" data-testid="song-editor">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-title font-semibold text-text-primary">Song</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            Draft writes title, album and lyrics. Polish rewrites the lyrics you have.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            loading={drafting}
            disabled={!draftEnabled || drafting}
            onClick={onDraft}
            data-testid="draft-button"
          >
            {drafting ? "Drafting..." : draftLabel}
          </Button>
          <Button
            variant="secondary"
            loading={polishing}
            disabled={!polishEnabled || polishing}
            onClick={onPolish}
            data-testid="polish-button"
          >
            {polishing ? "Polishing..." : polishLabel}
          </Button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
        <Meter label="Valence" value={effects.valence} testId="effect-valence" />
        <Meter label="Danceability" value={effects.danceability} testId="effect-danceability" />
        <Meter
          label="Instrumentalness"
          value={effects.instrumentalness}
          testId="effect-instrumentalness"
        />
        <RangeField
          id="music-polish-strength"
          label="Polish strength"
          value={settings.polishStrength}
          onChange={onPolishStrength}
          testId="polish-strength"
        />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <div className="col-span-2">
          <FieldLabel htmlFor="music-title">Title</FieldLabel>
          <Input
            id="music-title"
            className="mt-1"
            value={composer.title}
            placeholder="Song title"
            data-testid="song-title"
            onChange={(event) => onFieldChange({ title: event.target.value })}
          />
        </div>
        <div>
          <FieldLabel htmlFor="music-album">Album</FieldLabel>
          <Input
            id="music-album"
            className="mt-1"
            value={composer.album}
            placeholder="Album 1"
            data-testid="song-album"
            onChange={(event) => onFieldChange({ album: event.target.value })}
          />
        </div>
      </div>

      {seedNotice ? (
        <p
          className="mt-3 rounded-control border border-info/30 bg-info-soft px-3 py-2 text-meta text-text-secondary"
          data-testid="seed-notice"
        >
          {seedNotice}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          disabled={!hasTitle}
          onClick={() => onCopy("title")}
          data-testid="copy-title"
        >
          Copy title
        </Button>
        <Button
          variant="ghost"
          disabled={!hasLyrics}
          onClick={() => onCopy("lyrics")}
          data-testid="copy-lyrics"
        >
          Copy lyrics
        </Button>
        <Button
          variant="ghost"
          disabled={!hasTitle && !hasLyrics}
          onClick={() => onCopy("both")}
          data-testid="copy-both"
        >
          Copy both
        </Button>
        <Button
          variant="ghost"
          loading={polishing}
          disabled={!polishEnabled || polishing}
          onClick={onPolish}
          data-testid="rewrite-lyrics"
        >
          Rewrite lyrics
        </Button>
        {undoAvailable ? (
          <Button variant="ghost" onClick={onUndo} data-testid="undo-polish">
            Undo rewrite
          </Button>
        ) : null}
        <Button variant="ghost" disabled title="Revisions arrive with a later release">
          Revisions (0 credits)
        </Button>
      </div>

      <div className="mt-3 flex min-h-0 flex-1 flex-col">
        <div className="flex items-baseline justify-between gap-2">
          <FieldLabel htmlFor="music-lyrics">Lyrics</FieldLabel>
          <span
            className={overLimit ? "text-meta text-danger" : "text-meta text-text-muted"}
            data-testid="lyric-count"
          >
            {lyricLength.toLocaleString("en-US")} / {LYRIC_LIMIT.toLocaleString("en-US")} characters
          </span>
        </div>
        <textarea
          id="music-lyrics"
          data-testid="song-lyrics"
          className="mt-1 min-h-[220px] w-full flex-1 resize-y rounded-control border border-border bg-surface-1 p-3 text-body leading-6 text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
          value={composer.lyrics}
          placeholder="Write lyrics here"
          spellCheck={false}
          autoCorrect="off"
          autoCapitalize="off"
          onChange={(event) => onFieldChange({ lyrics: event.target.value })}
        />
        {overLimit ? (
          <p className="mt-1 text-meta text-danger">
            Lyrics exceed the {LYRIC_LIMIT.toLocaleString("en-US")} character backend limit.
          </p>
        ) : null}
      </div>
    </Card>
  );
}
