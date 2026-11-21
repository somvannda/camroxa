import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Icon } from "../../components/icon";
import { Input } from "../../components/input";
import { Badge, StatusDot } from "../../components/status";
import { classNames } from "../../lib/format";
import { toast } from "../../components/toast";
import { IMAGE_MODES, OUTPUT_RESOLUTIONS, profileInitials, type ProfileDraft } from "./settings-types";
import {
  ErrorBanner,
  KeyValueRow,
  Note,
  Section,
  SelectInput,
  Skeleton,
  TextInput,
} from "./settings-fields";
import type { SettingsWorkspace } from "./use-settings-workspace";

const YOUTUBE_STATUS: Record<string, { label: string; tone: "neutral" | "success" | "warning" | "danger" }> = {
  connected: { label: "Connected", tone: "success" },
  pending_browser: { label: "Waiting for browser sign-in", tone: "warning" },
  awaiting_channel_selection: { label: "Choose a channel", tone: "warning" },
  error: { label: "Connection issue", tone: "danger" },
  not_connected: { label: "Not connected", tone: "neutral" },
};

function youtubeConnectLabel(status: string): string {
  switch (status) {
    case "pending_browser":
      return "Restart sign-in";
    case "connected":
      return "Reconnect channel";
    case "error":
      return "Try again";
    case "awaiting_channel_selection":
      return "Start again";
    default:
      return "Connect channel";
  }
}

function youtubeHint(status: string, connectedName: string | null): string {
  if (status === "pending_browser") {
    return "Finish Google sign-in in your browser. If the flow was closed, use Restart sign-in.";
  }
  if (status === "awaiting_channel_selection") {
    return "Google returned more than one channel. Choose the channel for this profile.";
  }
  if (status === "error") {
    return "The previous attempt failed. Use Try again to start a fresh sign-in flow.";
  }
  if (status === "connected" && connectedName) {
    return `Uploads from this profile go to ${connectedName}.`;
  }
  return "Connect once here, then keep publication defaults in the Publication tab.";
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}

export function ProfilesTab({ workspace }: { workspace: SettingsWorkspace }) {
  const ws = workspace;
  const navigate = useNavigate();
  const [mediaBusy, setMediaBusy] = useState<"logo" | "cover" | null>(null);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [channelChoice, setChannelChoice] = useState("");

  const profileId = ws.isNewProfile ? null : ws.selectedProfileId;
  const profile = ws.selectedProfile;
  const connection = ws.youtubeConnection(profileId);
  const status = connection?.status ?? "not_connected";
  const statusMeta = YOUTUBE_STATUS[status] ?? YOUTUBE_STATUS.not_connected;
  const savingProfiles = ws.saving?.current === "profiles";
  const busy = Boolean(ws.saving);

  async function pickImage(kind: "logo" | "cover") {
    setMediaError(null);
    if (!window.camxora?.files) {
      setMediaError("Image pickers are only available in the desktop application.");
      return;
    }
    setMediaBusy(kind);
    try {
      const picked = await window.camxora.files.pick({
        kind: "file",
        title: kind === "logo" ? "Choose a profile logo" : "Choose a profile cover",
        filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg", "webp"] }],
      });
      if (!picked.ok) {
        setMediaError(picked.error.message);
        return;
      }
      const path = picked.data[0];
      if (!path) return;
      const read = await window.camxora.files.readImage(path);
      if (!read.ok) {
        setMediaError(read.error.message);
        return;
      }
      const base64 = bytesToBase64(read.data.bytes);
      const preview = `data:${read.data.mime};base64,${base64}`;
      const patch: Partial<ProfileDraft> =
        kind === "logo"
          ? { logoPath: path, logoBase64: base64, logoPreview: preview }
          : { coverPath: path, coverBase64: base64, coverPreview: preview };
      ws.updateProfileDraft(patch);
      toast(`${kind === "logo" ? "Logo" : "Cover"} selected. Save the profile to upload it.`, "info");
    } catch {
      setMediaError("The image could not be read.");
    } finally {
      setMediaBusy(null);
    }
  }

  const initials = profileInitials(ws.profileDraft.name || profile?.name || "Profile");
  const preview = ws.profileDraft.logoPreview;
  const hasLogoOnFile = Boolean(profile?.logo_path) || Boolean(ws.profileDraft.logoPath);
  const hasCoverOnFile = Boolean(profile?.image_config && profile.image_config.cover_paths);
  const editing = ws.isNewProfile || Boolean(profileId);

  const templateOptions = (kind: "long" | "reel", current: string) => {
    const list = ws.videoTemplates
      .filter((template) => template.kind === kind)
      .map((template) => ({
        value: template.id,
        label: `${template.name} · ${template.width}×${template.height}`,
      }));
    if (current && !list.some((option) => option.value === current)) {
      list.unshift({ value: current, label: "Unavailable template" });
    }
    if (!current) list.unshift({ value: "", label: "Choose a template" });
    return list;
  };

  if (ws.profilesError && ws.profiles.length === 0 && !ws.profilesLoading) {
    return (
      <div className="space-y-4" data-testid="settings-profiles-tab">
        <ErrorBanner
          message={`Unable to load channel profiles. ${ws.profilesError}`}
          onRetry={ws.retryProfiles}
        />
        {ws.tabErrors.profiles ? (
          <ErrorBanner
            message={ws.tabErrors.profiles}
            onRetry={() => ws.clearTabError("profiles")}
            retryLabel="Dismiss"
          />
        ) : null}
        <Card className="p-5">
          <p className="text-body text-text-secondary">
            Channel profiles could not be loaded. Retry to manage them.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="settings-profiles-tab">
      {ws.profilesError ? (
        <ErrorBanner
          message={`Unable to load channel profiles. ${ws.profilesError}`}
          onRetry={ws.retryProfiles}
        />
      ) : null}
      {ws.tabErrors.profiles ? (
        <ErrorBanner message={ws.tabErrors.profiles} onRetry={() => ws.clearTabError("profiles")} retryLabel="Dismiss" />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="h-fit p-3" data-testid="settings-profile-list">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h2 className="text-title font-semibold text-text-primary">Profiles</h2>
              <p className="text-caption text-text-muted font-mono text-tabular">
                {ws.profilesLoading ? "--" : ws.profileAllowanceText}
              </p>
            </div>
            <Button
              variant="primary"
              className="h-7 px-2.5"
              disabled={ws.profileLimitReached || ws.profilesLoading}
              onClick={ws.requestNewProfile}
            >
              New
            </Button>
          </div>

          <div className="relative mt-3">
            <Icon
              name="fa-magnifying-glass"
              size={14}
              className="pointer-events-none absolute left-2.5 top-2 text-text-muted"
            />
            <Input
              className="pl-8"
              aria-label="Search profiles"
              placeholder="Search name, folder or prefix"
              value={ws.profileSearch}
              onChange={(event) => ws.setProfileSearch(event.target.value)}
            />
          </div>

          {ws.profileLimitReached ? (
            <p className="mt-2 text-caption text-warning">
              Profile limit reached. Delete a profile or raise the allowance in the account portal.
            </p>
          ) : null}

          <div className="mt-2 space-y-0.5">
            {ws.profilesLoading ? (
              <Skeleton rows={3} />
            ) : ws.filteredProfiles.length === 0 ? (
              <p className="px-1 py-6 text-center text-meta text-text-muted">
                {ws.profiles.length === 0 ? "No profiles yet." : "No profiles match this search."}
              </p>
            ) : (
              ws.filteredProfiles.map((item) => {
                const active = !ws.isNewProfile && item.id === ws.selectedProfileId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-current={active ? "true" : undefined}
                    className={classNames(
                      "relative flex w-full items-center gap-2 rounded-[6px] px-2.5 py-2 text-left transition-colors",
                      active
                        ? "bg-surface-active text-text-primary"
                        : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                    )}
                    onClick={() => ws.requestSelectProfile(item)}
                  >
                    {active ? (
                      <span className="absolute left-0 top-2 h-5 w-0.5 rounded-full bg-accent" />
                    ) : null}
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-caption font-semibold text-accent">
                      {profileInitials(item.name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-body">{item.name}</span>
                      <span className="block truncate text-caption text-text-muted">
                        {item.folder_name || "no folder"}
                        {item.run_prefix ? ` · ${item.run_prefix}` : ""}
                      </span>
                    </span>
                  </button>
                );
              })
            )}
          </div>

          {ws.isNewProfile ? (
            <p className="mt-2 rounded-control border border-accent-line bg-accent-soft px-2.5 py-1.5 text-caption text-accent">
              New profile draft. Only the name is required.
            </p>
          ) : null}
        </Card>

        {ws.profilesLoading ? (
          <Card className="p-5" data-testid="settings-profiles-loading">
            <Skeleton rows={6} />
          </Card>
        ) : !editing ? (
          <Card className="flex min-h-[280px] flex-col items-center justify-center gap-3 p-8 text-center">
            <p className="text-body text-text-secondary">
              No profiles yet. Create one to set a folder, run prefix and YouTube channel.
            </p>
            <Button variant="primary" onClick={ws.requestNewProfile} disabled={ws.profileLimitReached}>
              New profile
            </Button>
          </Card>
        ) : (
          <div className="space-y-4">
            <Section
              title={ws.isNewProfile ? "New profile" : `Identity`}
              description={
                ws.isNewProfile
                  ? "Name the channel profile. Folder and run prefix can follow the name."
                  : "Name, output folder, run prefix and artwork used by batches."
              }
              action={
                <Badge tone={ws.profileDirty ? "warning" : "neutral"}>
                  {ws.isNewProfile ? "Draft" : ws.profileDirty ? "Unsaved" : "Saved"}
                </Badge>
              }
              data-testid="settings-profile-editor"
            >
              <div className="flex items-start gap-4">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-control border border-border bg-surface-2">
                  {preview ? (
                    <img src={preview} alt="Selected logo preview" className="h-full w-full object-cover" />
                  ) : (
                    <span className="text-title font-semibold text-accent">{initials}</span>
                  )}
                </div>
                <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-2">
                  <TextInput
                    id="settings-profile-name"
                    label="Name"
                    value={ws.profileDraft.name}
                    maxLength={100}
                    error={ws.profileErrors.name}
                    onChange={(event) => ws.updateProfileDraft({ name: event.target.value })}
                  />
                  <TextInput
                    id="settings-profile-folder"
                    label="Folder name"
                    value={ws.profileDraft.folderName}
                    maxLength={50}
                    error={ws.profileErrors.folderName}
                    hint="Follows the name until you edit it."
                    onChange={(event) => ws.updateProfileFolder(event.target.value)}
                  />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <TextInput
                  id="settings-profile-prefix"
                  label="Run prefix"
                  value={ws.profileDraft.runPrefix}
                  maxLength={24}
                  placeholder="Optional"
                  error={ws.profileErrors.runPrefix}
                  hint="Prefixes generated file names."
                  onChange={(event) => ws.updateProfileDraft({ runPrefix: event.target.value })}
                />
                <SelectInput
                  id="settings-profile-resolution"
                  label="Output resolution"
                  value={ws.profileDraft.outputResolution}
                  options={OUTPUT_RESOLUTIONS}
                  onChange={(event) =>
                    ws.updateProfileDraft({
                      outputResolution: event.target.value as ProfileDraft["outputResolution"],
                    })
                  }
                />
                <SelectInput
                  id="settings-profile-image-mode"
                  label="Image mode"
                  value={ws.profileDraft.imageMode}
                  options={IMAGE_MODES}
                  onChange={(event) =>
                    ws.updateProfileDraft({ imageMode: event.target.value as ProfileDraft["imageMode"] })
                  }
                />
              </div>

              {mediaError ? <ErrorBanner message={mediaError} onRetry={() => setMediaError(null)} retryLabel="Dismiss" /> : null}

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-control border border-border bg-surface-1 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-meta text-text-secondary">Logo</span>
                    {hasLogoOnFile ? <Badge tone="neutral">On file</Badge> : null}
                  </div>
                  <div className="mt-2 flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-[6px] border border-border bg-surface-2">
                      {preview ? (
                        <img src={preview} alt="Logo preview" className="h-full w-full object-cover" />
                      ) : (
                        <span className="text-meta font-semibold text-text-muted">{initials}</span>
                      )}
                    </div>
                    <Button
                      variant="secondary"
                      className="h-7 whitespace-nowrap px-2"
                      loading={mediaBusy === "logo"}
                      disabled={Boolean(mediaBusy) || busy}
                      onClick={() => void pickImage("logo")}
                    >
                      <Icon name="fa-image" size={14} />
                      {hasLogoOnFile ? "Replace logo" : "Choose logo"}
                    </Button>
                  </div>
                </div>

                <div className="rounded-control border border-border bg-surface-1 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-meta text-text-secondary">Cover</span>
                    {hasCoverOnFile ? <Badge tone="neutral">On file</Badge> : null}
                  </div>
                  <div className="mt-2 flex items-center gap-3">
                    <div className="flex h-10 w-14 items-center justify-center overflow-hidden rounded-[6px] border border-border bg-surface-2">
                      {ws.profileDraft.coverPreview ? (
                        <img
                          src={ws.profileDraft.coverPreview}
                          alt="Cover preview"
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <span className="text-caption text-text-muted">16:9</span>
                      )}
                    </div>
                    <Button
                      variant="secondary"
                      className="h-7 whitespace-nowrap px-2"
                      loading={mediaBusy === "cover"}
                      disabled={Boolean(mediaBusy) || busy}
                      onClick={() => void pickImage("cover")}
                    >
                      <Icon name="fa-image" size={14} />
                      {hasCoverOnFile ? "Replace cover" : "Choose cover"}
                    </Button>
                  </div>
                </div>
              </div>
              <p className="text-caption text-text-muted">
                Images upload when you save the profile. PNG, JPG or WebP, up to 25 MB.
              </p>
            </Section>

            <Section
              title="YouTube"
              description="The channel this profile publishes to."
              action={<StatusDot tone={statusMeta.tone} label={statusMeta.label} />}
              data-testid="settings-profile-youtube"
            >
              {ws.isNewProfile || !profile ? (
                <Note>Save the profile before connecting a YouTube channel.</Note>
              ) : (
                <>
                  <KeyValueRow
                    label="Channel"
                    value={connection?.channel_title ?? connection?.channel_id ?? "Not connected"}
                  />
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      variant={status === "connected" ? "secondary" : "primary"}
                      className="h-8"
                      loading={ws.youtubeBusy === "connect"}
                      disabled={Boolean(ws.youtubeBusy) || ws.pollingProfileId === profile.id}
                      onClick={() => ws.connectYoutube(profile.id)}
                    >
                      {youtubeConnectLabel(status)}
                    </Button>
                    {status !== "not_connected" ? (
                      <Button
                        variant="secondary"
                        className="h-8"
                        loading={ws.youtubeBusy === "disconnect"}
                        disabled={Boolean(ws.youtubeBusy)}
                        onClick={() => ws.requestDisconnectYoutube(profile)}
                      >
                        Disconnect
                      </Button>
                    ) : null}
                    <Button
                      variant="ghost"
                      className="h-8"
                      disabled={ws.connectionsLoading || Boolean(ws.youtubeBusy)}
                      onClick={ws.refreshConnections}
                    >
                      Refresh status
                    </Button>
                  </div>

                  {ws.pollingProfileId === profile.id ? (
                    <Note>Waiting for browser sign-in. This card updates when Google returns.</Note>
                  ) : (
                    <p className="text-caption text-text-muted">{youtubeHint(status, connection?.channel_title ?? null)}</p>
                  )}

                  {status === "awaiting_channel_selection" && (connection?.channels.length ?? 0) > 0 ? (
                    <div className="flex flex-wrap items-end gap-2 rounded-control border border-warning/30 bg-warning-soft p-3">
                      <div className="min-w-[220px] flex-1">
                        <SelectInput
                          id="settings-youtube-channel"
                          label="Channel"
                          value={channelChoice}
                          placeholder="Choose a channel"
                          options={(connection?.channels ?? []).map((channel) => ({
                            value: channel.id,
                            label: channel.title,
                          }))}
                          onChange={(event) => setChannelChoice(event.target.value)}
                        />
                      </div>
                      <Button
                        variant="primary"
                        className="h-8"
                        loading={ws.youtubeBusy === "select"}
                        disabled={!channelChoice || Boolean(ws.youtubeBusy)}
                        onClick={() => profile && ws.selectYoutubeChannel(profile.id, channelChoice)}
                      >
                        Use channel
                      </Button>
                    </div>
                  ) : null}

                  {ws.connectionsError ? (
                    <Note>Connection status could not be refreshed. The last known status is shown.</Note>
                  ) : null}
                </>
              )}
            </Section>

            <Section
              title="Video and reel templates"
              description="Choose this profile's long and reel template. Every saved template is listed below."
              data-testid="settings-profile-templates"
              action={
                <Button variant="ghost" className="h-7 px-2.5" onClick={() => navigate("/vizzy")}>
                  Open Vizzy
                </Button>
              }
            >
              {ws.videoTemplatesLoading ? (
                <Skeleton rows={1} />
              ) : (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <SelectInput
                      id="settings-profile-video-template"
                      label="Long video template"
                      value={ws.profileDraft.videoTemplateId}
                      options={templateOptions("long", ws.profileDraft.videoTemplateId)}
                      disabled={busy}
                      onChange={(event) =>
                        ws.updateProfileDraft({ videoTemplateId: event.target.value })
                      }
                    />
                    <SelectInput
                      id="settings-profile-reel-template"
                      label="Reel template"
                      value={ws.profileDraft.reelTemplateId}
                      options={templateOptions("reel", ws.profileDraft.reelTemplateId)}
                      disabled={busy}
                      onChange={(event) =>
                        ws.updateProfileDraft({ reelTemplateId: event.target.value })
                      }
                    />
                  </div>

                  {ws.videoTemplates.length === 0 ? (
                    <Note>
                      No saved video templates yet. Open Vizzy, preview a composition, then click
                      “Save template”.
                    </Note>
                  ) : (
                    <div
                      className="mt-3 max-h-[280px] space-y-1.5 overflow-auto pr-1"
                      data-testid="settings-profile-template-list"
                    >
                      {ws.videoTemplates.map((template) => {
                        const isLong = template.id === ws.profileDraft.videoTemplateId;
                        const isReel = template.id === ws.profileDraft.reelTemplateId;
                        return (
                          <div
                            key={template.id}
                            className={classNames(
                              "flex items-center gap-3 rounded-control border px-2.5 py-2",
                              isLong || isReel
                                ? "border-accent/40 bg-accent-soft/40"
                                : "border-border bg-surface-2",
                            )}
                          >
                            {template.thumbnailUrl ? (
                              <img
                                src={template.thumbnailUrl}
                                alt=""
                                className="h-9 w-14 shrink-0 rounded-[4px] object-cover"
                              />
                            ) : (
                              <span className="flex h-9 w-14 shrink-0 items-center justify-center rounded-[4px] bg-surface-3 text-text-muted">
                                <Icon name="fa-film" size={13} />
                              </span>
                            )}
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-meta font-medium text-text-primary">
                                {template.name}
                              </p>
                              <p className="text-caption text-text-muted">
                                {template.kind === "reel" ? "Reel" : "Long"} · {template.width}×
                                {template.height}
                              </p>
                            </div>
                            <div className="flex shrink-0 items-center gap-1.5">
                              {isLong ? <Badge tone="success">Long</Badge> : null}
                              {isReel ? <Badge tone="accent">Reel</Badge> : null}
                              {template.kind === "long" && !isLong ? (
                                <Button
                                  variant="ghost"
                                  className="h-7 px-2 text-caption"
                                  disabled={busy}
                                  onClick={() =>
                                    ws.updateProfileDraft({ videoTemplateId: template.id })
                                  }
                                >
                                  Use for long
                                </Button>
                              ) : null}
                              {template.kind === "reel" && !isReel ? (
                                <Button
                                  variant="ghost"
                                  className="h-7 px-2 text-caption"
                                  disabled={busy}
                                  onClick={() =>
                                    ws.updateProfileDraft({ reelTemplateId: template.id })
                                  }
                                >
                                  Use for reel
                                </Button>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  <p className="mt-2 text-caption text-text-muted">
                    Long and reel are saved separately with the profile. A template must be saved in
                    Vizzy before it appears here.
                  </p>
                </>
              )}
            </Section>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  loading={savingProfiles}
                  disabled={!ws.profileDirty || busy}
                  onClick={ws.saveProfiles}
                >
                  {ws.isNewProfile ? "Create profile" : "Save profile"}
                </Button>
                <Button
                  variant="secondary"
                  disabled={!ws.profileDirty || busy}
                  onClick={ws.discardProfiles}
                >
                  Cancel
                </Button>
              </div>
              <Button
                variant="secondary"
                className="text-danger"
                disabled={ws.isNewProfile || !profile || busy}
                onClick={() => profile && ws.requestDeleteProfile(profile)}
              >
                Delete profile
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
