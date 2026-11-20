import { Button } from "../../../components/button";
import { Card } from "../../../components/card";
import { StatusDot } from "../../../components/status";
import type { PlanCostBreakdown } from "../music-costs";
import { formatCredits, formatPlanLine } from "../music-costs";
import { saveStatusLabel } from "../music-settings";
import type { PromptOption, SaveStatus } from "../music-types";
import { CheckField, SelectField } from "./music-ui";

type ToggleKey =
  | "autoGenImage"
  | "autoGSuno"
  | "autoVideoAfterSuno"
  | "autoMergeAfterVideo"
  | "autoReelAfterVideo"
  | "autoUploadYouTube";

export interface PipelineNotice {
  tone: "success" | "warning" | "danger";
  text: string;
  /** Show the "Open Settings" link (missing template, missing audio). */
  settings?: boolean;
}

interface AutomationCardProps {
  descriptionId: string;
  structureId: string;
  descriptions: PromptOption[];
  structures: PromptOption[];
  onDescriptionChange: (id: string) => void;
  onStructureChange: (id: string) => void;
  toggles: Record<ToggleKey, boolean>;
  onToggle: (key: ToggleKey, value: boolean) => void;
  saveStatus: SaveStatus;
  unitCostLabels: string[];
  breakdown: PlanCostBreakdown | null;
  warnings: string[];
  batchSummary: string;
  batchStatus: string;
  batchStatusTone: "neutral" | "success" | "warning" | "danger";
  generating: boolean;
  generateEnabled: boolean;
  generateLabel: string;
  onGenerate: () => void;
  /** Video pipeline: resolved from the profile's saved templates. */
  pipelineSummary: string;
  pipelineJobCount: number;
  pipelineBusy: boolean;
  /** True when the plan is blocked by a missing template (show the Settings link). */
  pipelineNeedsSettings: boolean;
  pipelineNotice: PipelineNotice | null;
  onRenderVideos: () => void;
  onOpenSettings: () => void;
  /** Simple mode: Description + Songs per batch only. */
  simple?: boolean;
}

export function AutomationCard({
  descriptionId,
  structureId,
  descriptions,
  structures,
  onDescriptionChange,
  onStructureChange,
  toggles,
  onToggle,
  saveStatus,
  unitCostLabels,
  breakdown,
  warnings,
  batchSummary,
  batchStatus,
  batchStatusTone,
  generating,
  generateEnabled,
  generateLabel,
  onGenerate,
  pipelineSummary,
  pipelineJobCount,
  pipelineBusy,
  pipelineNeedsSettings,
  pipelineNotice,
  onRenderVideos,
  onOpenSettings,
  simple = false,
}: AutomationCardProps) {
  const pipelineSelected =
    toggles.autoVideoAfterSuno || toggles.autoMergeAfterVideo || toggles.autoReelAfterVideo;
  const saveTone =
    saveStatus === "saved" ? "success" : saveStatus === "error" ? "danger" : "neutral";
  const noticeTone =
    pipelineNotice?.tone === "danger"
      ? "text-danger"
      : pipelineNotice?.tone === "success"
        ? "text-success"
        : "text-warning";

  return (
    <Card className="flex min-h-0 min-w-0 flex-col p-4" data-testid="automation-card">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-title font-semibold text-text-primary">
          {simple ? "Simple generation" : "Automation"}
        </h2>
        <span data-testid="save-status" className="shrink-0">
          <StatusDot tone={saveTone} label={saveStatusLabel(saveStatus)} />
        </span>
      </div>

      {simple ? (
        <p className="mt-1 text-meta text-text-secondary">
          Only this Description and Songs per batch shape the run. Structure, mood, language,
          creativity and automation use their defaults.
        </p>
      ) : null}

      <div className="mt-3 space-y-2.5">
        <SelectField
          id="music-description"
          label={simple ? "Description prompt" : "Description"}
          value={descriptionId}
          options={
            descriptions.length === 0
              ? [{ value: "", label: "No descriptions available" }]
              : descriptions.map((option) => ({ value: option.id, label: option.name }))
          }
          onChange={onDescriptionChange}
          disabled={descriptions.length === 0}
          testId="automation-description"
        />
        {simple ? null : (
          <SelectField
            id="music-structure"
            label="Structure"
            value={structureId}
            options={
              structures.length === 0
                ? [{ value: "", label: "No structures available" }]
                : structures.map((option) => ({ value: option.id, label: option.name }))
            }
            onChange={onStructureChange}
            disabled={structures.length === 0}
            testId="automation-structure"
          />
        )}
      </div>

      {simple ? null : (
        <>
          <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 border-t border-border pt-3">
            <CheckField
              id="music-auto-image"
              label="Auto-Image"
              checked={toggles.autoGenImage}
              onChange={(value) => onToggle("autoGenImage", value)}
              testId="toggle-auto-image"
            />
            <CheckField
              id="music-auto-gsuno"
              label="Auto-GSuno"
              checked={toggles.autoGSuno}
              onChange={(value) => onToggle("autoGSuno", value)}
              testId="toggle-auto-gsuno"
            />
            <CheckField
              id="music-auto-video"
              label="Auto-Video"
              checked={toggles.autoVideoAfterSuno}
              onChange={(value) => onToggle("autoVideoAfterSuno", value)}
              testId="toggle-auto-video"
            />
            <CheckField
              id="music-auto-merge"
              label="Auto-Merge"
              checked={toggles.autoMergeAfterVideo}
              onChange={(value) => onToggle("autoMergeAfterVideo", value)}
              testId="toggle-auto-merge"
            />
            <CheckField
              id="music-auto-reel"
              label="Auto-Reel"
              checked={toggles.autoReelAfterVideo}
              onChange={(value) => onToggle("autoReelAfterVideo", value)}
              testId="toggle-auto-reel"
            />
            <div className="col-span-2">
              <CheckField
                id="music-auto-upload"
                label="Auto-Upload"
                checked={toggles.autoUploadYouTube}
                onChange={(value) => onToggle("autoUploadYouTube", value)}
                disabled
                hint="Stays disabled in 2.0, exactly as 1.7.1. Upload remains a manual step."
                testId="toggle-auto-upload"
              />
            </div>
          </div>

          {pipelineSelected ? (
            <p
              className="mt-2 rounded-control border border-warning/30 bg-warning-soft px-2.5 py-1.5 text-caption text-text-secondary"
              data-testid="pipeline-note"
            >
              Auto-Upload stays disabled. “Render videos” below queues the profile’s saved template
              for the ready songs and renders them without opening Vizzy.
            </p>
          ) : null}
        </>
      )}

      <div className="mt-3 rounded-control border border-border bg-surface-2 p-2.5">
        <p className="text-meta text-text-secondary" data-testid="plan-line">
          {formatPlanLine(breakdown)}
        </p>
        {breakdown ? (
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-caption">
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-text-muted">Total</dt>
              <dd className="text-text-primary text-tabular font-medium" data-testid="cost-total">
                {formatCredits(breakdown.total)}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-text-muted">Draft</dt>
              <dd className="text-text-secondary text-tabular" data-testid="cost-draft">
                {formatCredits(breakdown.draftTotal)}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-text-muted">Suno</dt>
              <dd className="text-text-secondary text-tabular" data-testid="cost-suno">
                {formatCredits(breakdown.sunoTotal)}
              </dd>
            </div>
            {simple ? null : (
              <>
                <div className="flex items-baseline justify-between gap-2">
                  <dt className="text-text-muted">Image</dt>
                  <dd className="text-text-secondary text-tabular" data-testid="cost-image">
                    {formatCredits(breakdown.imageTotal)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-2">
                  <dt className="text-text-muted">Video / merge</dt>
                  <dd className="text-text-secondary text-tabular" data-testid="cost-video">
                    {formatCredits(breakdown.videoMergeTotal)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-2">
                  <dt className="text-text-muted">Upload</dt>
                  <dd className="text-text-secondary text-tabular" data-testid="cost-upload">
                    {formatCredits(breakdown.uploadTotal)}
                  </dd>
                </div>
              </>
            )}
          </dl>
        ) : null}
        <div className="mt-2 flex flex-wrap gap-x-2.5 gap-y-0.5 border-t border-border pt-2 text-[11px] leading-4 text-text-muted">
          {unitCostLabels.map((label) => (
            <span key={label} data-testid={`unit-cost-${label.split(":")[0].toLowerCase()}`}>
              {label}
            </span>
          ))}
        </div>
      </div>

      {warnings.length > 0 ? (
        <ul className="mt-2 space-y-0.5 text-meta text-warning" data-testid="automation-warnings">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}

      <div className="sticky bottom-0 mt-3 border-t border-border bg-surface-1 pt-2">
        <Button
          variant="primary"
          className="h-10 w-full"
          loading={generating}
          disabled={!generateEnabled || generating}
          onClick={onGenerate}
          data-testid="generate-button"
        >
          {generating ? "Generating..." : generateLabel}
        </Button>

        {simple ? null : (
          <>
            <Button
              variant="secondary"
              className="mt-2 h-9 w-full"
              loading={pipelineBusy}
              disabled={pipelineBusy || generating}
              onClick={onRenderVideos}
              data-testid="render-videos-button"
            >
              {pipelineJobCount > 0
                ? `Render ${pipelineJobCount} video${pipelineJobCount === 1 ? "" : "s"}`
                : "Render videos"}
            </Button>

            <p className="mt-1.5 text-caption text-text-muted" data-testid="pipeline-summary">
              {pipelineSummary}
            </p>
            {pipelineNeedsSettings ? (
              <button
                type="button"
                className="mt-0.5 block text-caption text-accent underline hover:no-underline"
                onClick={onOpenSettings}
                data-testid="pipeline-settings-hint"
              >
                Open Settings
              </button>
            ) : null}

            {pipelineNotice ? (
              <div
                className={`mt-1 rounded-control border border-border bg-surface-2 px-2.5 py-1.5 text-caption ${noticeTone}`}
                role="status"
                data-testid="pipeline-message"
              >
                <span>{pipelineNotice.text}</span>
                {pipelineNotice.settings ? (
                  <button
                    type="button"
                    className="ml-1 underline hover:no-underline"
                    onClick={onOpenSettings}
                    data-testid="pipeline-settings-link"
                  >
                    Open Settings
                  </button>
                ) : null}
              </div>
            ) : null}
          </>
        )}

        {batchSummary || batchStatus ? (
          <div className="mt-2 space-y-0.5 text-caption">
            {batchSummary ? (
              <p className="text-text-secondary" data-testid="batch-summary">
                {batchSummary}
              </p>
            ) : null}
            {batchStatus ? (
              <p className="text-text-muted" data-testid="batch-status">
                <StatusDot tone={batchStatusTone} label={batchStatus} />
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}
