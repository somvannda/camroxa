import { useState } from "react";
import { Button } from "../../components/button";
import { Badge, StatusDot } from "../../components/status";
import {
  HOURS,
  MAX_DESCRIPTION_CHARS,
  MAX_KEYWORDS_CHARS,
  MAX_TITLE_TEMPLATE_CHARS,
  MAX_TAGS_COUNT,
  MINUTES,
  PUBLICATION_CATEGORIES,
  VISIBILITY_OPTIONS,
  parseCommaList,
  renderTemplate,
  scheduleSummary,
  type PublicationDraft,
} from "./settings-types";
import {
  CheckboxInput,
  ErrorBanner,
  KeyValueRow,
  Note,
  Section,
  SelectInput,
  Skeleton,
  TextAreaInput,
  TextInput,
} from "./settings-fields";
import type { SettingsWorkspace } from "./use-settings-workspace";

const SAMPLE_VALUES = {
  title: "Neon Skyline",
  album: "Night Drive",
  channel: "Night Shift",
};

export function PublicationTab({ workspace }: { workspace: SettingsWorkspace }) {
  const ws = workspace;
  const [newPlaylist, setNewPlaylist] = useState("");
  const draft = ws.publicationDraft;
  const savingPublication = ws.saving?.current === "publication";
  const busy = Boolean(ws.saving);

  const scheduled = draft.visibility === "scheduled";
  const summary = scheduleSummary(draft);
  const connectionStatus = ws.publicationConnection?.status ?? "not_connected";
  const connected = ws.publicationConnected;
  const keywordsText = parseCommaList(draft.keywords).join(", ");
  const tagsList = parseCommaList(draft.tags);

  const playlistsLoaded = !ws.playlistsLoading && !ws.playlistsError;
  const savedPlaylistInList = ws.playlists.some((playlist) => playlist.id === draft.playlist);
  const playlistOptions = [
    ...ws.playlists.map((playlist) => ({ value: playlist.id, label: playlist.title })),
    ...(draft.playlist && !savedPlaylistInList
      ? [
          {
            value: draft.playlist,
            label: playlistsLoaded ? "Saved playlist (not on channel)" : "Saved playlist",
          },
        ]
      : []),
  ];

  async function createPlaylist() {
    if (!newPlaylist.trim() || ws.playlistBusy) return;
    await ws.createPlaylist(newPlaylist);
    setNewPlaylist("");
  }

  if (ws.profilesLoading) {
    return (
      <div data-testid="settings-publication-loading">
        <Section title="Publication" description="Profile-specific YouTube publishing defaults.">
          <Skeleton rows={6} />
        </Section>
      </div>
    );
  }

  if (ws.profilesError && ws.profiles.length === 0 && !ws.profilesLoading) {
    return (
      <div className="space-y-4" data-testid="settings-publication-tab">
        <ErrorBanner
          message={`Unable to load channel profiles. ${ws.profilesError}`}
          onRetry={ws.retryProfiles}
        />
        <Section title="Publication" description="Profile-specific YouTube publishing defaults.">
          <p className="text-body text-text-secondary">
            Publication settings need a channel profile. Profiles could not be loaded.
          </p>
        </Section>
      </div>
    );
  }

  if (ws.profiles.length === 0) {
    return (
      <div className="space-y-4" data-testid="settings-publication-tab">
        <Section
          title="Publication"
          description="Profile-specific YouTube publishing defaults."
        >
          <Note>Create a channel profile before setting publication defaults.</Note>
          <div>
            <Button variant="primary" onClick={() => ws.setActiveTab("profiles")}>
              Open Profiles
            </Button>
          </div>
        </Section>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="settings-publication-tab">
      {ws.profilesError ? (
        <ErrorBanner
          message={`Unable to load channel profiles. ${ws.profilesError}`}
          onRetry={ws.retryProfiles}
        />
      ) : null}
      {ws.tabErrors.publication ? (
        <ErrorBanner
          message={ws.tabErrors.publication}
          onRetry={() => ws.clearTabError("publication")}
          retryLabel="Dismiss"
        />
      ) : null}

      <Section
        title="Profile"
        description="Publication defaults are stored on the selected profile."
        action={
          <Badge tone={ws.publicationDirty ? "warning" : "neutral"}>
            {ws.publicationDirty ? "Unsaved" : "Saved"}
          </Badge>
        }
        data-testid="settings-publication-profile"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectInput
            id="settings-publication-profile-select"
            label="Channel profile"
            value={ws.publicationProfileId ?? ""}
            options={ws.profiles.map((profile) => ({ value: profile.id, label: profile.name }))}
            onChange={(event) => ws.requestPublicationProfile(event.target.value)}
          />
          <div className="rounded-control border border-border bg-surface-1 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-meta text-text-secondary">YouTube</span>
              <StatusDot
                tone={connected ? "success" : connectionStatus === "error" ? "danger" : "neutral"}
                label={
                  connected
                    ? ws.publicationConnection?.channel_title ?? "Connected"
                    : connectionStatus === "pending_browser"
                      ? "Waiting for sign-in"
                      : connectionStatus === "error"
                        ? "Connection issue"
                        : "Not connected"
                }
              />
            </div>
            <div className="mt-2">
              {connected ? (
                <p className="text-caption text-text-muted">
                  Playlists load from {ws.publicationConnection?.channel_title ?? "the channel"}.
                </p>
              ) : (
                <div className="space-y-2">
                  <p className="text-caption text-text-muted">
                    Publication values still save. Uploads stay blocked until a channel is connected
                    on the Profiles tab.
                  </p>
                  <Button
                    variant="secondary"
                    className="h-7 px-2.5"
                    onClick={() => ws.setActiveTab("profiles")}
                  >
                    Open Profiles
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </Section>

      <Section title="Visibility and schedule" description="Defaults for every upload from this profile.">
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectInput
            id="settings-publication-visibility"
            label="Visibility"
            value={draft.visibility}
            options={VISIBILITY_OPTIONS}
            onChange={(event) =>
              ws.updatePublicationDraft({ visibility: event.target.value as PublicationDraft["visibility"] })
            }
          />
          <SelectInput
            id="settings-publication-category"
            label="Category"
            value={draft.category}
            options={PUBLICATION_CATEGORIES}
            onChange={(event) => ws.updatePublicationDraft({ category: event.target.value })}
          />
        </div>

        <div>
          <div className="grid gap-3 sm:grid-cols-[110px_110px_auto] sm:items-end">
            <SelectInput
              id="settings-publication-hour"
              label="Hour"
              value={draft.publishHour}
              options={HOURS}
              disabled={!scheduled}
              error={ws.publicationErrors.publishHour}
              onChange={(event) => ws.updatePublicationDraft({ publishHour: event.target.value })}
            />
            <SelectInput
              id="settings-publication-minute"
              label="Minute"
              value={draft.publishMinute}
              options={MINUTES}
              disabled={!scheduled}
              error={ws.publicationErrors.publishMinute}
              onChange={(event) => ws.updatePublicationDraft({ publishMinute: event.target.value })}
            />
            <Button
              variant="secondary"
              className="h-8 justify-self-start"
              disabled={!scheduled || (draft.publishHour === "00" && draft.publishMinute === "00")}
              onClick={() => ws.updatePublicationDraft({ publishHour: "00", publishMinute: "00" })}
            >
              Clear
            </Button>
          </div>
          <p className="mt-2 text-caption text-text-muted">
            {scheduled
              ? `Scheduled uploads use the run date and the saved time ${draft.publishHour}:${draft.publishMinute} (local). Next matching slot: ${summary}.`
              : "This only applies when visibility is set to Scheduled."}
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <CheckboxInput
            id="settings-publication-kids"
            label="Made for kids"
            checked={draft.madeForKids}
            onChange={(event) => ws.updatePublicationDraft({ madeForKids: event.target.checked })}
          />
          <SelectInput
            id="settings-publication-ai"
            label="AI use disclosure"
            value={draft.aiUse ? "yes" : "no"}
            options={[
              { value: "no", label: "No" },
              { value: "yes", label: "Yes" },
            ]}
            onChange={(event) => ws.updatePublicationDraft({ aiUse: event.target.value === "yes" })}
          />
        </div>
      </Section>

      <Section title="Playlist" description="Optional playlist for uploads from this profile.">
        {ws.playlistsError ? (
          <ErrorBanner
            message={`Playlists could not be loaded. The rest of this tab still saves. ${ws.playlistsError}`}
            onRetry={ws.retryPlaylists}
          />
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectInput
            id="settings-publication-playlist"
            label="Playlist"
            value={draft.playlist}
            options={playlistOptions}
            placeholder="No playlist"
            disabled={!connected || ws.playlistsLoading}
            error={ws.publicationErrors.playlist}
            hint={
              connected
                ? ws.playlistsLoading
                  ? "Loading playlists…"
                  : "Leave empty to upload without a playlist."
                : "Connect a channel to choose a playlist."
            }
            onChange={(event) => ws.updatePublicationDraft({ playlist: event.target.value })}
          />
          <div className="flex items-end gap-2">
            <div className="min-w-0 flex-1">
              <TextInput
                id="settings-publication-new-playlist"
                label="New playlist"
                placeholder="Playlist name"
                value={newPlaylist}
                maxLength={150}
                disabled={!connected || ws.playlistBusy}
                onChange={(event) => setNewPlaylist(event.target.value)}
              />
            </div>
            <Button
              variant="secondary"
              className="h-8"
              loading={ws.playlistBusy}
              disabled={!connected || !newPlaylist.trim() || ws.playlistBusy}
              onClick={() => void createPlaylist()}
            >
              Create playlist
            </Button>
          </div>
        </div>
        {connected ? null : (
          <Note>No channel is connected for this profile, so the channel playlist list is unavailable.</Note>
        )}
      </Section>

      <Section title="Metadata" description="Defaults written to each upload.">
        <TextAreaInput
          id="settings-publication-description"
          label="Channel description"
          rows={4}
          value={draft.description}
          disabled={busy}
          maxLength={MAX_DESCRIPTION_CHARS}
          error={ws.publicationErrors.description}
          hint={`${draft.description.length} / ${MAX_DESCRIPTION_CHARS}`}
          onChange={(event) => ws.updatePublicationDraft({ description: event.target.value })}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput
            id="settings-publication-keywords"
            label="Keywords"
            placeholder="lofi, night drive, focus"
            value={draft.keywords}
            disabled={busy}
            error={ws.publicationErrors.keywords}
            hint={`Comma separated. ${keywordsText.length} / ${MAX_KEYWORDS_CHARS} characters.`}
            onChange={(event) => ws.updatePublicationDraft({ keywords: event.target.value })}
          />
          <TextInput
            id="settings-publication-tags"
            label="Tags"
            placeholder="chill, instrumental"
            value={draft.tags}
            disabled={busy}
            error={ws.publicationErrors.tags}
            hint={`Comma separated. ${tagsList.length} / ${MAX_TAGS_COUNT} tags.`}
            onChange={(event) => ws.updatePublicationDraft({ tags: event.target.value })}
          />
        </div>
      </Section>

      <Section
        title="Title and description templates"
        description="Tokens: {title}, {album}, {channel}. The preview uses sample values."
      >
        <TextInput
          id="settings-publication-title-template"
          label="Title template"
          placeholder="{title} (Official Audio)"
          value={draft.titleTemplate}
          disabled={busy}
          maxLength={MAX_TITLE_TEMPLATE_CHARS}
          error={ws.publicationErrors.titleTemplate}
          onChange={(event) => ws.updatePublicationDraft({ titleTemplate: event.target.value })}
        />
        <div className="rounded-control border border-border bg-surface-2 px-3 py-2">
          <p className="text-caption text-text-muted">Title preview</p>
          <p className="truncate text-body text-text-primary">
            {renderTemplate(draft.titleTemplate, SAMPLE_VALUES) || "No title template"}
          </p>
        </div>

        <TextAreaInput
          id="settings-publication-description-template"
          label="Description template"
          rows={3}
          value={draft.descriptionTemplate}
          disabled={busy}
          maxLength={MAX_DESCRIPTION_CHARS}
          error={ws.publicationErrors.descriptionTemplate}
          onChange={(event) => ws.updatePublicationDraft({ descriptionTemplate: event.target.value })}
        />
        <div className="rounded-control border border-border bg-surface-2 px-3 py-2">
          <p className="text-caption text-text-muted">Description preview</p>
          <p className="whitespace-pre-wrap text-body text-text-primary">
            {renderTemplate(draft.descriptionTemplate, SAMPLE_VALUES) || "No description template"}
          </p>
        </div>
      </Section>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            loading={savingPublication}
            disabled={!ws.publicationDirty || busy || !ws.publicationProfileId}
            onClick={ws.savePublication}
          >
            Save publication
          </Button>
          <Button
            variant="secondary"
            disabled={!ws.publicationDirty || busy}
            onClick={ws.discardPublication}
          >
            Revert
          </Button>
          {ws.publicationDirty ? (
            <span className="text-caption text-warning">Unsaved changes</span>
          ) : null}
        </div>
        {ws.publicationDirty ? null : (
          <KeyValueRow
            label="Last save"
            value={ws.lastSavedAt ? new Date(ws.lastSavedAt).toLocaleTimeString() : "Not saved this session"}
          />
        )}
      </div>
    </div>
  );
}
