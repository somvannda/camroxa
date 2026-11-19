import { Button } from "../../components/button";
import { Badge } from "../../components/status";
import {
  SUNO_MERGE_GROUP_MAX,
  SUNO_MERGE_GROUP_MIN,
  SUNO_RETRY_MAX,
  SUNO_RETRY_MIN,
  SUNO_TIMEOUT_MAX_MS,
  SUNO_TIMEOUT_MIN_MS,
  SUNO_VERSION_OPTIONS,
  isSupportedSunoVersion,
} from "./settings-types";
import {
  CheckboxInput,
  ErrorBanner,
  KeyValueRow,
  Note,
  NumberInput,
  Section,
  SelectInput,
  Skeleton,
} from "./settings-fields";
import type { SettingsWorkspace } from "./use-settings-workspace";

export function SunoTab({ workspace }: { workspace: SettingsWorkspace }) {
  const ws = workspace;
  const draft = ws.sunoDraft;
  const savingSuno = ws.saving?.current === "suno";
  const busy = Boolean(ws.saving);

  if (ws.settingsLoading) {
    return (
      <div className="space-y-4" data-testid="settings-suno-tab">
        <div data-testid="settings-suno-loading">
          <Section title="Suno defaults" description="Runtime values used when a music batch runs.">
            <Skeleton rows={5} />
          </Section>
        </div>
      </div>
    );
  }

  if (ws.settingsError) {
    return (
      <div className="space-y-4" data-testid="settings-suno-tab">
        <ErrorBanner message={`Unable to load Suno defaults. ${ws.settingsError}`} onRetry={ws.retrySettings} />
      </div>
    );
  }

  const versionOptions: Array<{ value: string; label: string }> = SUNO_VERSION_OPTIONS.map((version) => ({
    value: version,
    label: version,
  }));
  const unsupported = draft.defaultVersion && !isSupportedSunoVersion(draft.defaultVersion);
  if (unsupported) {
    versionOptions.unshift({
      value: draft.defaultVersion,
      label: `${draft.defaultVersion} · not supported`,
    });
  }

  return (
    <div className="space-y-4" data-testid="settings-suno-tab">
      {ws.tabErrors.suno ? (
        <ErrorBanner
          message={ws.tabErrors.suno}
          onRetry={() => ws.clearTabError("suno")}
          retryLabel="Dismiss"
        />
      ) : null}

      <Section
        title="Suno defaults"
        description="Runtime values used when a music batch runs."
        action={<Badge tone={ws.sunoDirty ? "warning" : "neutral"}>{ws.sunoDirty ? "Unsaved" : "Saved"}</Badge>}
        data-testid="settings-suno-form"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectInput
            id="settings-suno-version"
            label="Default Suno version"
            value={draft.defaultVersion}
            options={versionOptions}
            error={ws.sunoErrors.defaultVersion}
            disabled={busy}
            onChange={(event) => ws.updateSuno({ defaultVersion: event.target.value })}
          />
          <div className="flex items-end pb-1">
            <CheckboxInput
              id="settings-suno-merge"
              label="Auto merge downloads"
              hint="Merge the generated tracks of a group into one file after download."
              checked={draft.mergeEnabled}
              disabled={busy}
              onChange={(event) => ws.updateSuno({ mergeEnabled: event.target.checked })}
            />
          </div>
          <NumberInput
            id="settings-suno-merge-group"
            label="Merge group size"
            min={SUNO_MERGE_GROUP_MIN}
            max={SUNO_MERGE_GROUP_MAX}
            step={1}
            value={draft.mergeGroupSize}
            error={ws.sunoErrors.mergeGroupSize}
            hint={`${SUNO_MERGE_GROUP_MIN}–${SUNO_MERGE_GROUP_MAX}; used only when auto merge is on.`}
            disabled={busy}
            onChange={(event) => ws.updateSuno({ mergeGroupSize: Number(event.target.value) })}
          />
          <NumberInput
            id="settings-suno-timeout"
            label="Timeout (ms)"
            min={SUNO_TIMEOUT_MIN_MS}
            max={SUNO_TIMEOUT_MAX_MS}
            step={1000}
            value={draft.timeoutMs}
            error={ws.sunoErrors.timeoutMs}
            hint={`${SUNO_TIMEOUT_MIN_MS}–${SUNO_TIMEOUT_MAX_MS} ms per request.`}
            disabled={busy}
            onChange={(event) => ws.updateSuno({ timeoutMs: Number(event.target.value) })}
          />
          <NumberInput
            id="settings-suno-retry"
            label="Retry count"
            min={SUNO_RETRY_MIN}
            max={SUNO_RETRY_MAX}
            step={1}
            value={draft.retryCount}
            error={ws.sunoErrors.retryCount}
            hint={`${SUNO_RETRY_MIN}–${SUNO_RETRY_MAX} retries after a failed request.`}
            disabled={busy}
            onChange={(event) => ws.updateSuno({ retryCount: Number(event.target.value) })}
          />
        </div>

        <Note>
          Only the supported Suno defaults are shown here. Values outside the allowed bounds block the
          save and are reported under the field.
        </Note>
        <Note>
          These keys are stored in your account settings. Save all changes writes only the values that
          changed and leaves every other setting untouched.
        </Note>
        {unsupported ? (
          <Note tone="warning">
            The stored version {draft.defaultVersion} is not supported by this build. Choose a listed
            version before saving.
          </Note>
        ) : null}
      </Section>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            loading={savingSuno}
            disabled={!ws.sunoDirty || busy}
            onClick={ws.saveSuno}
            data-testid="settings-suno-save"
          >
            Save Suno
          </Button>
          <Button variant="secondary" disabled={!ws.sunoDirty || busy} onClick={ws.discardSuno}>
            Revert
          </Button>
        </div>
        {ws.sunoDirty ? (
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
