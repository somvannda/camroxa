import { Card } from "../../../components/card";
import { Badge } from "../../../components/status";
import {
  HISTORY_WINDOW_OPTIONS,
  LANGUAGE_OPTIONS,
  SONG_COUNT_MAX,
  SONG_COUNT_MIN,
  type MusicSettings,
} from "../music-settings";
import { plannedDaysText, inclusiveDaySpan } from "../music-format";
import { CheckField, DateField, NumberField, RangeField, SelectField } from "./music-ui";

interface MusicSettingsStripProps {
  settings: MusicSettings;
  fromDate: string;
  toDate: string;
  onFromDate: (value: string) => void;
  onToDate: (value: string) => void;
  onSettingsChange: (patch: Partial<MusicSettings>) => void;
}

export function MusicSettingsStrip({
  settings,
  fromDate,
  toDate,
  onFromDate,
  onToDate,
  onSettingsChange,
}: MusicSettingsStripProps) {
  const invalidRange = inclusiveDaySpan(fromDate, toDate) === null;

  return (
    <Card className="p-4" data-testid="settings-strip">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-title font-semibold text-text-primary">Run settings</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            Defaults for drafting and the planned batch range. Changes save automatically.
          </p>
        </div>
        <div className="shrink-0" data-testid="planned-days">
          <Badge tone={invalidRange ? "danger" : "accent"}>
            {plannedDaysText(fromDate, toDate)}
          </Badge>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <DateField
          id="music-from-date"
          label="From"
          value={fromDate}
          onChange={onFromDate}
          invalid={invalidRange}
          testId="music-from-date"
        />
        <DateField
          id="music-to-date"
          label="To"
          value={toDate}
          onChange={onToDate}
          invalid={invalidRange}
          testId="music-to-date"
        />
        <SelectField
          id="music-language"
          label="Language"
          value={settings.language}
          options={LANGUAGE_OPTIONS.map((option) => ({ value: option.value, label: option.label }))}
          onChange={(value) => onSettingsChange({ language: value })}
          testId="music-language"
        />
        <RangeField
          id="music-creativity"
          label="Creativity"
          value={settings.creativity}
          onChange={(value) => onSettingsChange({ creativity: value })}
          className="xl:col-span-2"
          testId="music-creativity"
        />
        <div className="flex items-end pb-1">
          <CheckField
            id="music-unique-opening"
            label="Unique opening"
            checked={settings.uniqueOpening}
            onChange={(checked) => onSettingsChange({ uniqueOpening: checked })}
            testId="music-unique-opening"
          />
        </div>
        <SelectField
          id="music-strict"
          label="Strict"
          value={settings.strictLevel}
          options={[1, 2, 3, 4, 5].map((level) => ({ value: level, label: String(level) }))}
          onChange={(value) => onSettingsChange({ strictLevel: Number(value) })}
          testId="music-strict"
        />
        <SelectField
          id="music-history-window"
          label="History window"
          value={settings.historyWindow}
          options={HISTORY_WINDOW_OPTIONS.map((size) => ({ value: size, label: String(size) }))}
          onChange={(value) => onSettingsChange({ historyWindow: Number(value) })}
          testId="music-history-window"
        />
        <NumberField
          id="music-count"
          label="Songs per batch"
          value={settings.songCount}
          min={SONG_COUNT_MIN}
          max={SONG_COUNT_MAX}
          onChange={(value) =>
            onSettingsChange({
              songCount: Math.min(SONG_COUNT_MAX, Math.max(SONG_COUNT_MIN, value)),
            })
          }
          testId="music-count"
        />
        <div className="flex items-end pb-1">
          <CheckField
            id="music-use-pools"
            label="Use content pools"
            checked={settings.useContentPools}
            onChange={(checked) => onSettingsChange({ useContentPools: checked })}
            testId="music-use-pools"
          />
        </div>
      </div>

      {invalidRange ? (
        <p className="mt-3 text-meta text-danger" role="alert">
          To must be on or after From. Generate is disabled until the range is valid.
        </p>
      ) : null}
    </Card>
  );
}
