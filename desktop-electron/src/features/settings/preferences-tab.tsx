import { useState } from "react";
import { Button } from "../../components/button";
import { Icon } from "../../components/icon";
import { Badge, StatusDot } from "../../components/status";
import { toast } from "../../components/toast";
import { openExternal } from "../auth/portal";
import {
  KIND_SOURCES,
  OUTPUT_RESOLUTIONS,
  THUMBNAIL_GENERATIONS,
  YOUTUBE_CHUNK_SIZES,
  workerLoadWarning,
  type PreferencesDraft,
} from "./settings-types";
import {
  ErrorBanner,
  InlineWarning,
  KeyValueRow,
  Note,
  NumberInput,
  Section,
  SelectInput,
  Skeleton,
  TextInput,
} from "./settings-fields";
import type { SettingsWorkspace } from "./use-settings-workspace";

const FFMPEG_DOWNLOAD_URL = "https://ffmpeg.org/download.html";

function PathRow({
  id,
  label,
  value,
  kind,
  hint,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  kind: "file" | "directory";
  hint: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const [busy, setBusy] = useState<"browse" | "open" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function browse() {
    setError(null);
    if (!window.camxora?.files) {
      setError("File pickers are only available in the desktop application.");
      return;
    }
    setBusy("browse");
    try {
      const picked = await window.camxora.files.pick({
        kind,
        title: label,
      });
      if (!picked.ok) {
        setError(picked.error.message);
        return;
      }
      if (picked.data[0]) onChange(picked.data[0]);
    } catch {
      setError("The picker could not be opened.");
    } finally {
      setBusy(null);
    }
  }

  async function open() {
    setError(null);
    if (!value.trim()) {
      setError("Choose a path first.");
      return;
    }
    if (!window.camxora?.files) {
      setError("Opening paths is only available in the desktop application.");
      return;
    }
    setBusy("open");
    try {
      const result = await window.camxora.files.open(value.trim());
      if (!result.ok) setError(result.error.message);
    } catch {
      setError("The path could not be opened.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <TextInput
        id={id}
        label={label}
        value={value}
        mono
        hint={hint}
        error={error ?? undefined}
        disabled={disabled}
        placeholder={kind === "directory" ? "C:\\path\\to\\folder" : "C:\\path\\to\\ffmpeg.exe"}
        onChange={(event) => onChange(event.target.value)}
      />
      <div className="mt-2 flex flex-wrap gap-2">
        <Button
          variant="secondary"
          className="h-7 px-2.5"
          loading={busy === "browse"}
          disabled={disabled || Boolean(busy)}
          onClick={() => void browse()}
        >
          Browse
        </Button>
        <Button
          variant="ghost"
          className="h-7 px-2.5"
          loading={busy === "open"}
          disabled={disabled || Boolean(busy) || !value.trim()}
          onClick={() => void open()}
        >
          <Icon name="fa-folder-open" size={14} />
          Open
        </Button>
      </div>
    </div>
  );
}

export function PreferencesTab({ workspace }: { workspace: SettingsWorkspace }) {
  const ws = workspace;
  const draft = ws.preferencesDraft;
  const savingPreferences = ws.saving?.current === "preferences";
  const busy = Boolean(ws.saving);
  const workerWarning = workerLoadWarning(draft);
  const [diagnosticsBusy, setDiagnosticsBusy] = useState(false);
  const [diagnosticsId, setDiagnosticsId] = useState<string | null>(null);
  const [diagnosticsError, setDiagnosticsError] = useState<string | null>(null);

  async function sendDiagnostics() {
    setDiagnosticsBusy(true);
    setDiagnosticsError(null);
    try {
      if (!window.camxora?.diagnostics) {
        setDiagnosticsError("Diagnostics are only available in the desktop application.");
        return;
      }
      const result = await window.camxora.diagnostics.send();
      if (!result.ok) {
        setDiagnosticsError(result.error.message);
        return;
      }
      setDiagnosticsId(result.data.uploadId);
      toast("Diagnostics bundle prepared.", "success");
    } catch {
      setDiagnosticsError("Diagnostics could not be prepared.");
    } finally {
      setDiagnosticsBusy(false);
    }
  }

  if (ws.settingsLoading) {
    return (
      <div className="space-y-4" data-testid="settings-preferences-tab">
        <div data-testid="settings-preferences-loading">
          <Section title="Local paths" description="Executable and output folders on this computer.">
            <Skeleton rows={4} />
          </Section>
        </div>
        <Section title="Workers" description="Concurrency used by music, images, export, merge and upload.">
          <Skeleton rows={3} />
        </Section>
      </div>
    );
  }

  if (ws.settingsError) {
    return (
      <div className="space-y-4" data-testid="settings-preferences-tab">
        <ErrorBanner
          message={`Unable to load preferences. ${ws.settingsError}`}
          onRetry={ws.retrySettings}
        />
      </div>
    );
  }

  const sourceOptions = ws.promptLibraryOnly
    ? KIND_SOURCES.filter((option) => option.value === "admin_library")
    : KIND_SOURCES;
  const aiMode = draft.imageSourceMode === "ai";

  return (
    <div className="space-y-4" data-testid="settings-preferences-tab">
      {ws.tabErrors.preferences ? (
        <ErrorBanner
          message={ws.tabErrors.preferences}
          onRetry={() => ws.clearTabError("preferences")}
          retryLabel="Dismiss"
        />
      ) : null}

      <Section
        title="Local paths"
        description="Executable and output folders on this computer."
        action={
          <Badge tone={ws.preferencesDirty ? "warning" : "neutral"}>
            {ws.preferencesDirty ? "Unsaved" : "Saved"}
          </Badge>
        }
        data-testid="settings-preferences-paths"
      >
        <PathRow
          id="settings-preferences-ffmpeg"
          label="FFmpeg path"
          value={draft.ffmpegPath}
          kind="file"
          hint="Leave empty to use the FFmpeg resolved by the desktop app."
          disabled={busy}
          onChange={(value) => ws.updatePreferences({ ffmpegPath: value })}
        />
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-border bg-surface-1 px-3 py-2">
          <StatusDot
            tone={
              ws.ffmpegStatus.state === "available"
                ? "success"
                : ws.ffmpegStatus.state === "missing"
                  ? "warning"
                  : "neutral"
            }
            label={ws.ffmpegStatus.message}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="ghost"
              className="h-7 px-2.5"
              disabled={ws.ffmpegStatus.state === "checking"}
              onClick={ws.checkFfmpeg}
            >
              Check again
            </Button>
            <Button
              variant="secondary"
              className="h-7 px-2.5"
              onClick={() => {
                void openExternal(FFMPEG_DOWNLOAD_URL).then((failure) => {
                  if (failure) toast(failure, "danger");
                });
              }}
            >
              Download FFmpeg
            </Button>
          </div>
        </div>
        <p className="text-caption text-text-muted">
          The build resolves its bundled FFmpeg first. A custom path is saved with your settings and
          used when it points at a working binary.
        </p>

        <PathRow
          id="settings-preferences-suno"
          label="Suno output dir"
          value={draft.sunoOutputDir}
          kind="directory"
          hint="Batch folders are created under this root."
          disabled={busy}
          onChange={(value) => ws.updatePreferences({ sunoOutputDir: value })}
        />
        <Note>
          Batch folders use {"{channel}/{date_album}"} under this root, with shared subfolders for
          audio, images and renders. Saving creates the folder when it is missing.
        </Note>
        {ws.preferencesWarnings.map((warning) => (
          <InlineWarning key={warning}>{warning}</InlineWarning>
        ))}
      </Section>

      <Section
        title="Workers"
        description="Concurrency used by music, images, export, merge and upload."
        data-testid="settings-preferences-workers"
      >
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <NumberInput
            id="settings-preferences-music-workers"
            label="Music workers"
            min={1}
            max={5}
            value={draft.musicWorkers}
            error={ws.preferencesErrors.musicWorkers}
            disabled={busy}
            onChange={(event) => ws.updatePreferences({ musicWorkers: Number(event.target.value) })}
          />
          <NumberInput
            id="settings-preferences-image-workers"
            label="Image workers"
            min={1}
            max={8}
            value={draft.imageWorkers}
            error={ws.preferencesErrors.imageWorkers}
            disabled={busy}
            onChange={(event) => ws.updatePreferences({ imageWorkers: Number(event.target.value) })}
          />
          <NumberInput
            id="settings-preferences-export-workers"
            label="Export workers"
            min={1}
            max={10}
            value={draft.exportWorkers}
            error={ws.preferencesErrors.exportWorkers}
            disabled={busy}
            onChange={(event) => ws.updatePreferences({ exportWorkers: Number(event.target.value) })}
          />
          <NumberInput
            id="settings-preferences-merge-workers"
            label="Merge workers"
            min={1}
            max={2}
            value={draft.mergeWorkers}
            error={ws.preferencesErrors.mergeWorkers}
            disabled={busy}
            onChange={(event) => ws.updatePreferences({ mergeWorkers: Number(event.target.value) })}
          />
          <NumberInput
            id="settings-preferences-youtube-workers"
            label="YouTube workers"
            min={1}
            max={5}
            value={draft.youtubeWorkers}
            error={ws.preferencesErrors.youtubeWorkers}
            disabled={busy}
            onChange={(event) => ws.updatePreferences({ youtubeWorkers: Number(event.target.value) })}
          />
          <SelectInput
            id="settings-preferences-chunk"
            label="Upload chunk size"
            value={String(draft.chunkSizeMb)}
            options={YOUTUBE_CHUNK_SIZES.map((size) => ({ value: String(size), label: `${size} MB` }))}
            error={ws.preferencesErrors.chunkSizeMb}
            disabled={busy}
            onChange={(event) => ws.updatePreferences({ chunkSizeMb: Number(event.target.value) })}
          />
        </div>
        {workerWarning ? <Note tone="warning">{workerWarning}</Note> : null}
        <Note>
          Worker counts are saved with your account settings. The rendering pipeline arrives in P7 and
          reads these values when a batch runs; until then they do not change any running work.
        </Note>
      </Section>

      <Section
        title="Image and rendering"
        description="Defaults for image generation and thumbnails."
        data-testid="settings-preferences-rendering"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectInput
            id="settings-preferences-resolution"
            label="Output resolution"
            value={draft.outputResolution}
            options={OUTPUT_RESOLUTIONS}
            disabled={busy}
            onChange={(event) =>
              ws.updatePreferences({
                outputResolution: event.target.value as PreferencesDraft["outputResolution"],
              })
            }
          />
          <SelectInput
            id="settings-preferences-image-source"
            label="Image source mode"
            value={draft.imageSourceMode}
            options={[
              { value: "ai", label: "AI Generated" },
              { value: "manual", label: "User Provided" },
            ]}
            disabled={busy}
            onChange={(event) =>
              ws.updatePreferences({
                imageSourceMode: event.target.value as PreferencesDraft["imageSourceMode"],
              })
            }
          />
        </div>

        <div>
          <label className="mb-1.5 block text-meta text-text-secondary" htmlFor="settings-preferences-style">
            Style strength
          </label>
          <div className="flex items-center gap-3">
            <input
              id="settings-preferences-style"
              type="range"
              min={0}
              max={100}
              step={1}
              value={draft.styleStrength}
              disabled={busy}
              className="h-4 w-full accent-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50"
              onChange={(event) => ws.updatePreferences({ styleStrength: Number(event.target.value) })}
            />
            <span className="w-14 shrink-0 text-right font-mono text-meta text-text-primary text-tabular">
              {draft.styleStrength} / 100
            </span>
          </div>
          {ws.preferencesErrors.styleStrength ? (
            <p className="mt-1 text-caption text-danger" role="alert">
              {ws.preferencesErrors.styleStrength}
            </p>
          ) : null}
        </div>

        {aiMode ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectInput
              id="settings-preferences-background-source"
              label="Background source"
              value={draft.backgroundSource}
              options={sourceOptions}
              disabled={busy || ws.promptLibraryOnly}
              onChange={(event) =>
                ws.updatePreferences({
                  backgroundSource: event.target.value as PreferencesDraft["backgroundSource"],
                })
              }
            />
            <SelectInput
              id="settings-preferences-thumbnail-source"
              label="Thumbnail source"
              value={draft.thumbnailSource}
              options={sourceOptions}
              disabled={busy || ws.promptLibraryOnly}
              onChange={(event) =>
                ws.updatePreferences({
                  thumbnailSource: event.target.value as PreferencesDraft["thumbnailSource"],
                })
              }
            />
          </div>
        ) : (
          <Note>
            User Provided skips AI image generation. Place the final images in the run folder and the
            pipeline continues with them.
          </Note>
        )}

        <SelectInput
          id="settings-preferences-thumbnail-generation"
          label="Thumbnail generation"
          value={draft.thumbnailGeneration}
          options={THUMBNAIL_GENERATIONS}
          disabled={busy}
          onChange={(event) =>
            ws.updatePreferences({
              thumbnailGeneration: event.target.value as PreferencesDraft["thumbnailGeneration"],
            })
          }
        />

        <Note>
          AI Generated pairs a Background/Thumbnail source with My prompt or the Admin prompt library:
          Category uses admin samples, Prompt only uses text, and Admin library uses the admin prompt
          library. AI text on background renders the thumbnail text on the generated background.
          Style strength applies when a Category sample is used.
        </Note>

        {ws.promptLibraryOnly ? (
          <Note>
            The account is limited to the Admin prompt library, so the source is fixed to Admin library.
          </Note>
        ) : null}

        <Note>
          Background and thumbnail samples are managed on the server. Local sample-pack downloads and
          the local sample library are not part of this build.
        </Note>
      </Section>

      <Section title="Storage" description="Local audio-analysis cache used by preview and export.">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-control border border-border bg-surface-1 p-3">
            <p className="text-meta text-text-secondary">Audio analysis cache</p>
            <p className="mt-1 text-body text-text-primary">Managed by the P7 pipeline</p>
            <p className="mt-1 text-caption text-text-muted">
              The cache size and the clear action arrive with the pipeline. Nothing is cleared from
              this build.
            </p>
          </div>
          <div className="rounded-control border border-border bg-surface-1 p-3">
            <p className="text-meta text-text-secondary">Cache policy</p>
            <p className="mt-1 text-body text-text-primary">2 GB · 30 days</p>
            <p className="mt-1 text-caption text-text-muted">
              The pipeline keeps recently used tracks up to 2 GB and drops entries unused for 30 days.
            </p>
          </div>
        </div>
      </Section>

      <Section title="Diagnostics" description="Application logs and environment information.">
        <div className="flex items-start gap-2 text-body text-text-secondary">
          <Icon name="fa-shield-halved" size={16} className="mt-0.5 shrink-0 text-text-muted" />
          <p>
            Logs stay on this computer until you send them. A bundle contains app and OS versions plus
            recent redacted log lines.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            className="h-8"
            loading={diagnosticsBusy}
            disabled={diagnosticsBusy}
            onClick={() => void sendDiagnostics()}
          >
            <Icon name="fa-upload" size={14} />
            Send diagnostics
          </Button>
          {diagnosticsId ? (
            <span className="inline-flex items-center gap-1.5 text-meta text-success">
              <Icon name="fa-circle-check" size={14} />
              Prepared · <span className="font-mono text-tabular">{diagnosticsId}</span>
            </span>
          ) : null}
        </div>
        {diagnosticsError ? <ErrorBanner message={diagnosticsError} /> : null}
        <Note>
          This build writes the diagnostics reference locally. Uploading the bundle to the support
          service is not enabled yet.
        </Note>
      </Section>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            loading={savingPreferences}
            disabled={!ws.preferencesDirty || busy}
            onClick={ws.savePreferences}
          >
            Save preferences
          </Button>
          <Button
            variant="secondary"
            disabled={!ws.preferencesDirty || busy}
            onClick={ws.discardPreferences}
          >
            Revert
          </Button>
        </div>
        {ws.preferencesDirty ? (
          <span className="text-caption text-warning">Unsaved changes</span>
        ) : (
          <KeyValueRow
            label="Last save"
            value={ws.lastSavedAt ? new Date(ws.lastSavedAt).toLocaleTimeString() : "Not saved this session"}
          />
        )}
      </div>
    </div>
  );
}
