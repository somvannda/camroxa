"use client";

import Link from "next/link";
import * as React from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, ArrowRight, FolderKanban, Image as ImageIcon, Youtube } from "lucide-react";

import { useControlPanel } from "@/components/dashboard/control-panel-provider";
import {
  EmptyPanel,
  InlineBadge,
  MusicBatchCard,
  SectionTitle,
  SummaryRow,
  formatDateTime,
  getCoverCount,
  getInitials,
  hasYouTubeConnection,
} from "@/components/dashboard/control-panel-ui";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { updateProfile } from "@/lib/channel-setup";
import {
  loadProfileCoverObjectUrl,
  loadProfileLogoObjectUrl,
} from "@/lib/profile-media";
import {
  disconnectYouTubeConnection,
  listYouTubeConnections,
  resyncYouTubeConnection,
  startYouTubeConnection,
  type YouTubeConnection,
} from "@/lib/youtube";

export default function DashboardProfileDetailPage() {
  const params = useParams<{ profileId: string }>();
  const { state, setState } = useControlPanel();
  const profileId = String(params?.profileId ?? "");
  const profile = state.profiles.find((item) => item.id === profileId) ?? null;
  const [name, setName] = React.useState("");
  const [folderName, setFolderName] = React.useState("");
  const [runPrefix, setRunPrefix] = React.useState("");
  const [outputResolution, setOutputResolution] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [youtubeConnection, setYouTubeConnection] = React.useState<YouTubeConnection | null>(null);
  const [youtubeBusy, setYouTubeBusy] = React.useState<"connect" | "resync" | "disconnect" | null>(null);
  const [logoObjectUrl, setLogoObjectUrl] = React.useState<string | null>(null);
  const [coverObjectUrls, setCoverObjectUrls] = React.useState<string[]>([]);
  const [pendingLogoBase64, setPendingLogoBase64] = React.useState<string | null>(null);
  const [pendingLogoName, setPendingLogoName] = React.useState("");
  const [pendingCoverImages, setPendingCoverImages] = React.useState<string[]>([]);
  const [pendingCoverNames, setPendingCoverNames] = React.useState<string[]>([]);
  const [savingAssets, setSavingAssets] = React.useState(false);

  const relatedBatches = React.useMemo(
    () =>
      (state.musicHistory?.batches ?? []).filter(
        (batch) => batch.ok_profile_id === profileId || batch.alt_profile_id === profileId,
      ),
    [profileId, state.musicHistory?.batches],
  );

  React.useEffect(() => {
    setName(profile?.name ?? "");
    setFolderName(profile?.folder_name ?? "");
    setRunPrefix(profile?.run_prefix ?? "");
    setOutputResolution(profile?.output_resolution ?? "1920x1080");
  }, [profile?.folder_name, profile?.name, profile?.output_resolution, profile?.run_prefix]);

  if (!profile) {
    return (
      <div className="grid gap-6">
        <SectionTitle
          title="Profile Detail"
          description="This profile could not be found in the current account context."
        />
        <EmptyPanel text="The requested profile is not available. Return to the main profiles page and choose another profile." />
      </div>
    );
  }

  const stableProfileId = profile.id;
  const coverCount = getCoverCount(profile.image_config);
  const youtubeConnected = hasYouTubeConnection(profile.youtube_config) || Boolean(youtubeConnection?.channel_id);
  const coverPaths = Array.isArray(profile.image_config?.cover_paths)
    ? profile.image_config.cover_paths.filter((value): value is string => typeof value === "string")
    : [];
  const youtubeConfig = profile.youtube_config ?? {};
  const currentChannelId = youtubeConnection?.channel_id ?? youtubeConfig.channel_id;
  const currentChannelTitle = youtubeConnection?.channel_title ?? youtubeConfig.channel_title;
  const currentConnectionStatus = youtubeConnection?.status ?? (youtubeConnected ? "linked" : "pending");

  React.useEffect(() => {
    let cancelled = false;
    let nextLogoUrl: string | null = null;
    const nextCoverUrls: string[] = [];

    async function loadAssetsAndConnection() {
      try {
        const connections = await listYouTubeConnections().catch(() => []);
        if (!cancelled) {
          setYouTubeConnection(
            connections.find((connection) => connection.profile_id === stableProfileId) ?? null,
          );
        }
      } catch {}

      nextLogoUrl = await loadProfileLogoObjectUrl(stableProfileId).catch(() => null);
      for (let index = 0; index < coverCount; index += 1) {
        const nextUrl = await loadProfileCoverObjectUrl(stableProfileId, index).catch(() => null);
        if (nextUrl) {
          nextCoverUrls.push(nextUrl);
        }
      }

      if (!cancelled) {
        setLogoObjectUrl((current) => {
          if (current) URL.revokeObjectURL(current);
          return nextLogoUrl;
        });
        setCoverObjectUrls((current) => {
          current.forEach((url) => URL.revokeObjectURL(url));
          return nextCoverUrls;
        });
      } else {
        if (nextLogoUrl) URL.revokeObjectURL(nextLogoUrl);
        nextCoverUrls.forEach((url) => URL.revokeObjectURL(url));
      }
    }

    void loadAssetsAndConnection();

    return () => {
      cancelled = true;
    };
  }, [coverCount, profile.logo_path, profile.updated_at, stableProfileId]);

  async function handleSave() {
    const nextName = name.trim();
    if (!nextName) {
      toast({
        variant: "destructive",
        title: "Profile name required",
        description: "Enter a profile name before saving.",
      });
      return;
    }

    setSaving(true);
    try {
      const updated = await updateProfile(stableProfileId, {
        name: nextName,
        folder_name: folderName.trim() || null,
        run_prefix: runPrefix.trim() || null,
        output_resolution: outputResolution.trim() || null,
      });
      setState((current) => ({
        ...current,
        profiles: current.profiles.map((item) => (item.id === updated.id ? updated : item)),
      }));
      toast({
        title: "Profile updated",
        description: "Profile settings have been saved.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to update this profile.";
      toast({ variant: "destructive", title: "Update failed", description: message });
    } finally {
      setSaving(false);
    }
  }

  async function handleLogoSelection(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (!file) {
      setPendingLogoBase64(null);
      setPendingLogoName("");
      return;
    }

    try {
      setPendingLogoBase64(await fileToBase64(file));
      setPendingLogoName(file.name);
    } catch {
      toast({
        variant: "destructive",
        title: "Logo upload failed",
        description: "Unable to read the selected logo file.",
      });
    }
  }

  async function handleCoverSelection(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []).slice(0, 5);
    if (files.length === 0) {
      setPendingCoverImages([]);
      setPendingCoverNames([]);
      return;
    }

    try {
      const nextImages = await Promise.all(files.map((file) => fileToBase64(file)));
      setPendingCoverImages(nextImages);
      setPendingCoverNames(files.map((file) => file.name));
    } catch {
      toast({
        variant: "destructive",
        title: "Cover upload failed",
        description: "Unable to read the selected cover files.",
      });
    }
  }

  async function handleSaveAssets() {
    if (!pendingLogoBase64 && pendingCoverImages.length === 0) {
      toast({
        variant: "destructive",
        title: "No asset changes",
        description: "Choose a logo or cover images before saving.",
      });
      return;
    }

    setSavingAssets(true);
    try {
      const updated = await updateProfile(stableProfileId, {
        logo_base64: pendingLogoBase64,
        cover_images: pendingCoverImages.length > 0 ? pendingCoverImages : undefined,
      });
      setState((current) => ({
        ...current,
        profiles: current.profiles.map((item) => (item.id === updated.id ? updated : item)),
      }));
      setPendingLogoBase64(null);
      setPendingLogoName("");
      setPendingCoverImages([]);
      setPendingCoverNames([]);
      toast({
        title: "Assets updated",
        description: "Logo and cover assets have been replaced successfully.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to update profile assets.";
      toast({ variant: "destructive", title: "Asset update failed", description: message });
    } finally {
      setSavingAssets(false);
    }
  }

  async function handleYouTubeConnect() {
    setYouTubeBusy("connect");
    try {
      const result = await startYouTubeConnection(stableProfileId);
      window.location.href = result.auth_url;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to start the YouTube connection flow.";
      toast({ variant: "destructive", title: "YouTube connect failed", description: message });
      setYouTubeBusy(null);
    }
  }

  async function handleYouTubeResync() {
    setYouTubeBusy("resync");
    try {
      const result = await resyncYouTubeConnection(stableProfileId);
      setYouTubeConnection(result);
      setState((current) => ({
        ...current,
        profiles: current.profiles.map((item) =>
          item.id === stableProfileId
            ? {
                ...item,
                youtube_config: {
                  ...(item.youtube_config ?? {}),
                  channel_id: result.channel_id ?? null,
                  channel_title: result.channel_title ?? null,
                },
              }
            : item,
        ),
      }));
      toast({
        title: "YouTube refreshed",
        description: result.message ?? "The YouTube connection has been refreshed.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to refresh the YouTube connection.";
      toast({ variant: "destructive", title: "Resync failed", description: message });
    } finally {
      setYouTubeBusy(null);
    }
  }

  async function handleYouTubeDisconnect() {
    setYouTubeBusy("disconnect");
    try {
      await disconnectYouTubeConnection(stableProfileId);
      setYouTubeConnection(null);
      setState((current) => ({
        ...current,
        profiles: current.profiles.map((item) =>
          item.id === stableProfileId
            ? {
                ...item,
                youtube_config: {},
              }
            : item,
        ),
      }));
      toast({
        title: "YouTube disconnected",
        description: "This profile is no longer linked to a YouTube channel.",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to disconnect the YouTube channel.";
      toast({ variant: "destructive", title: "Disconnect failed", description: message });
    } finally {
      setYouTubeBusy(null);
    }
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle
          title={profile.name}
          description="Inspect per-profile readiness, production settings, and recent output activity."
        />
        <Button
          variant="outline"
          asChild
          className="border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06]"
        >
          <Link href="/dashboard/profiles">
            <ArrowLeft className="h-4 w-4" />
            Back to profiles
          </Link>
        </Button>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(340px,0.86fr)_minmax(0,1.14fr)]">
        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(18,28,70,0.96),rgba(10,14,34,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.38)]">
          <CardHeader className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500/80 via-purple-500/70 to-fuchsia-500/70 text-base font-semibold text-white shadow-[0_14px_40px_rgba(118,77,255,0.22)]">
                {getInitials(profile.name)}
              </div>
              <div>
                <CardTitle className="font-display text-2xl text-white">{profile.name}</CardTitle>
                <CardDescription className="text-slate-300/72">
                  Production identity summary for this profile.
                </CardDescription>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <InlineBadge text={profile.logo_path ? "Logo ready" : "Logo pending"} tone={profile.logo_path ? "emerald" : "amber"} />
              <InlineBadge text={`${coverCount} covers`} tone="blue" />
              <InlineBadge text={youtubeConnected ? "YouTube linked" : "YouTube pending"} tone={youtubeConnected ? "emerald" : "amber"} />
            </div>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm text-slate-300/72">
            <SummaryRow label="Folder" value={profile.folder_name ?? "Not configured"} />
            <SummaryRow label="Run prefix" value={profile.run_prefix ?? "Not configured"} />
            <SummaryRow label="Resolution" value={profile.output_resolution ?? "1920x1080"} />
            <SummaryRow label="Video template" value={profile.video_template_id ?? "Not configured"} />
            <SummaryRow label="Reel template" value={profile.reel_template_id ?? "Not configured"} />
            <SummaryRow label="Updated" value={formatDateTime(profile.updated_at)} />
          </CardContent>
        </Card>

        <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] shadow-[0_24px_80px_rgba(33,16,64,0.2)] ring-1 ring-white/6">
          <CardHeader>
            <CardTitle className="font-display text-2xl text-white">Asset and connection detail</CardTitle>
            <CardDescription className="text-slate-300/72">
              Deeper visibility into asset inventory and connection configuration for this profile.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                <div className="flex items-center gap-2 text-sm font-medium text-white">
                  <ImageIcon className="h-4 w-4 text-sky-200" />
                  Cover assets
                </div>
                <div className="mt-3 text-2xl font-semibold text-white">{coverCount}</div>
                <div className="mt-2 text-sm text-slate-300/72">
                  Saved cover variations currently attached to this profile.
                </div>
              </div>
              <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                <div className="flex items-center gap-2 text-sm font-medium text-white">
                  <Youtube className="h-4 w-4 text-rose-200" />
                  YouTube connection
                </div>
                <div className="mt-3 text-2xl font-semibold text-white">
                  {youtubeConnected ? "Linked" : "Pending"}
                </div>
                <div className="mt-2 text-sm text-slate-300/72">
                  {youtubeConnected ? "This profile includes channel linkage data for upload workflows." : "Connect this profile before relying on upload automation."}
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Button type="button" onClick={() => void handleYouTubeConnect()} disabled={youtubeBusy !== null}>
                    {youtubeBusy === "connect" ? "Connecting..." : youtubeConnected ? "Reconnect YouTube" : "Connect YouTube"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void handleYouTubeResync()}
                    disabled={youtubeBusy !== null || !youtubeConnected}
                    className="border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06]"
                  >
                    {youtubeBusy === "resync" ? "Refreshing..." : "Resync"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void handleYouTubeDisconnect()}
                    disabled={youtubeBusy !== null || !youtubeConnected}
                    className="border-white/10 bg-white/[0.03] text-white hover:bg-white/[0.06]"
                  >
                    {youtubeBusy === "disconnect" ? "Disconnecting..." : "Disconnect"}
                  </Button>
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                <div className="text-sm font-medium text-white">Saved asset previews</div>
                <div className="mt-3 grid gap-3 text-sm text-slate-300/72">
                  <div>
                    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">Logo</div>
                    {logoObjectUrl ? (
                      <img
                        src={logoObjectUrl}
                        alt={`${profile.name} logo`}
                        className="h-24 w-24 rounded-2xl border border-white/10 object-cover"
                      />
                    ) : (
                      <EmptyPanel text="No saved logo preview available." />
                    )}
                  </div>
                  <div>
                    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-500">Covers</div>
                    {coverObjectUrls.length > 0 ? (
                      <div className="grid grid-cols-2 gap-3">
                        {coverObjectUrls.map((url, index) => (
                          <img
                            key={`${url}-${index}`}
                            src={url}
                            alt={`${profile.name} cover ${index + 1}`}
                            className="h-24 w-full rounded-2xl border border-white/10 object-cover"
                          />
                        ))}
                      </div>
                    ) : coverPaths.length > 0 ? (
                      coverPaths.slice(0, 5).map((path) => (
                        <div key={path} className="truncate rounded-xl border border-white/8 bg-black/10 px-3 py-2">
                          {path}
                        </div>
                      ))
                    ) : (
                      <EmptyPanel text="No saved covers are available yet." />
                    )}
                  </div>
                </div>
              </div>

              <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5">
                <div className="text-sm font-medium text-white">Channel connection fields</div>
                <div className="mt-3 grid gap-2 text-sm text-slate-300/72">
                  <SummaryRow label="Status" value={stringValue(currentConnectionStatus)} />
                  <SummaryRow label="Channel ID" value={stringValue(currentChannelId)} />
                  <SummaryRow label="Selected channel" value={stringValue(youtubeConfig.selected_channel_id)} />
                  <SummaryRow label="Channel name" value={stringValue(youtubeConfig.channel_name)} />
                  <SummaryRow label="Channel title" value={stringValue(currentChannelTitle)} />
                  <SummaryRow label="Connection message" value={stringValue(youtubeConnection?.message)} />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
        <CardHeader>
          <CardTitle className="font-display text-2xl text-white">Replace logo and covers</CardTitle>
          <CardDescription className="text-slate-300/72">
            Upload replacement assets for this profile using the authenticated update flow.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="grid gap-2">
            <Label className="text-slate-100" htmlFor="profile_logo_upload">
              Replace logo
            </Label>
            <Input
              id="profile_logo_upload"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) => void handleLogoSelection(event)}
              className="border-white/10 bg-white/[0.04] text-white file:border-0 file:bg-transparent file:text-slate-300"
            />
            <div className="text-xs text-slate-400">
              {pendingLogoName ? `Selected: ${pendingLogoName}` : "Choose a new logo image for this profile."}
            </div>
          </div>

          <div className="grid gap-2">
            <Label className="text-slate-100" htmlFor="profile_cover_upload">
              Replace covers
            </Label>
            <Input
              id="profile_cover_upload"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              multiple
              onChange={(event) => void handleCoverSelection(event)}
              className="border-white/10 bg-white/[0.04] text-white file:border-0 file:bg-transparent file:text-slate-300"
            />
            <div className="text-xs text-slate-400">
              {pendingCoverNames.length > 0
                ? `Selected: ${pendingCoverNames.join(", ")}`
                : "Choose up to 5 cover images to replace the existing set."}
            </div>
          </div>

          <div className="md:col-span-2">
            <Button onClick={() => void handleSaveAssets()} disabled={savingAssets}>
              {savingAssets ? "Saving assets..." : "Save asset replacements"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
        <CardHeader>
          <CardTitle className="font-display text-2xl text-white">Editable profile settings</CardTitle>
          <CardDescription className="text-slate-300/72">
            Update the core naming and output settings tied to this profile.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="grid gap-2">
            <Label className="text-slate-100" htmlFor="profile_name">
              Profile name
            </Label>
            <Input
              id="profile_name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="border-white/10 bg-white/[0.04] text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
            />
          </div>
          <div className="grid gap-2">
            <Label className="text-slate-100" htmlFor="profile_folder_name">
              Folder name
            </Label>
            <Input
              id="profile_folder_name"
              value={folderName}
              onChange={(event) => setFolderName(event.target.value)}
              className="border-white/10 bg-white/[0.04] text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
            />
          </div>
          <div className="grid gap-2">
            <Label className="text-slate-100" htmlFor="profile_run_prefix">
              Run prefix
            </Label>
            <Input
              id="profile_run_prefix"
              value={runPrefix}
              onChange={(event) => setRunPrefix(event.target.value)}
              className="border-white/10 bg-white/[0.04] text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
            />
          </div>
          <div className="grid gap-2">
            <Label className="text-slate-100" htmlFor="profile_output_resolution">
              Output resolution
            </Label>
            <Input
              id="profile_output_resolution"
              value={outputResolution}
              onChange={(event) => setOutputResolution(event.target.value)}
              className="border-white/10 bg-white/[0.04] text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
            />
          </div>
          <div className="md:col-span-2">
            <Button onClick={() => void handleSave()} disabled={saving}>
              {saving ? "Saving..." : "Save profile settings"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
        <CardHeader>
          <CardTitle className="font-display text-2xl text-white">Related production history</CardTitle>
          <CardDescription className="text-slate-300/72">
            Recent music batches connected to this profile as a primary or alternate output target.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {relatedBatches.length > 0 ? (
            relatedBatches.map((batch) => (
              <MusicBatchCard key={batch.batch_id} batch={batch} />
            ))
          ) : (
            <EmptyPanel text="No recent music batches are linked to this profile yet." />
          )}
        </CardContent>
      </Card>

      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(16,22,52,0.94),rgba(9,12,28,0.98))] shadow-[0_24px_80px_rgba(18,24,58,0.3)]">
        <CardHeader>
          <CardTitle className="font-display text-2xl text-white">Profile actions</CardTitle>
          <CardDescription className="text-slate-300/72">
            Use the main profiles area or account settings to continue operational management.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <Link
            href="/dashboard/profiles"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-violet-400/25 hover:bg-violet-500/[0.08]"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <FolderKanban className="h-4 w-4 text-violet-200" />
              Return to profiles
            </div>
            <div className="mt-2 text-sm text-slate-300/72">
              Go back to the full profile list and compare readiness across all channels.
            </div>
          </Link>
          <Link
            href="/dashboard/activity"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-sky-400/25 hover:bg-sky-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">Open activity</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Review recent production events and batch output tied to this account.
            </div>
          </Link>
          <Link
            href="/dashboard/security"
            className="rounded-[24px] border border-white/10 bg-white/[0.03] p-5 transition hover:border-emerald-400/25 hover:bg-emerald-500/[0.08]"
          >
            <div className="text-sm font-medium text-white">Review account controls</div>
            <div className="mt-2 text-sm text-slate-300/72">
              Keep sign-in and account settings aligned before production changes.
            </div>
            <div className="mt-4 flex items-center gap-2 text-sm text-emerald-200">
              Open controls
              <ArrowRight className="h-4 w-4" />
            </div>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

function stringValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value : "Not configured";
}

async function fileToBase64(file: File) {
  const buffer = await file.arrayBuffer();
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return window.btoa(binary);
}
