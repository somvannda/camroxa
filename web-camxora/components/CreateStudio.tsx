"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/components/AuthProvider";
import { usePlayer } from "@/components/PlayerProvider";
import { cn } from "@/lib/utils";
import type { WebMusicClip, WebMusicGeneration } from "@/lib/library-api";
import {
  WebMusicApiError,
  addWebMusicPlaylistItem,
  clipFilename,
  createWebMusicPlaylist,
  createWebMusicWorkspace,
  deleteWebMusicGeneration,
  fetchWebMusicClipBlob,
  fetchWebMusicClipWavBlob,
  fetchWebMusicQuota,
  fetchWebMusicTimedLyricsBlob,
  generateWebMusic,
  generateWebMusicDraft,
  generateWebMusicStyles,
  getWebMusicGeneration,
  listWebMusicGenerations,
  listWebMusicPlaylists,
  listWebMusicWorkspaces,
  saveBlob,
  unlockWebMusicPreview,
  updateWebMusicGenerationTitle,
  updateWebMusicWorkspace,
  type WebMusicGenerateInput,
  type WebMusicModel,
  type WebMusicPlaylistSummary,
  type WebMusicQuota,
  type WebMusicWorkspace,
} from "@/lib/web-music-api";
import { createStoreZip, type ZipEntry } from "@/lib/zip-store";

type Mode = "simple" | "custom";
type LyricsMode = "write" | "prompt";

const models: Array<{ value: WebMusicModel; label: string }> = [
  { value: "V6", label: "V6 Pro" },
  { value: "V6_MINI", label: "V6 Mini" },
  { value: "V6_WILD", label: "V6 Wild" },
];

const SIMPLE_SONG_COUNTS = [1, 5, 10, 20] as const;
const BATCH_SUBMIT_GAP_MS = 900;
const DOWNLOAD_FORMATS: Array<{ value: DownloadKind; label: string }> = [
  { value: "mp3", label: "MP3" },
  { value: "wav", label: "WAV" },
  { value: "lrc", label: "LRC" },
  { value: "srt", label: "SRT" },
];

const styleChips = [
  "pop",
  "rock",
  "hip hop",
  "electronic",
  "khmer",
  "acoustic",
  "synthwave",
  "rnb",
  "jazz",
  "ambient",
  "dance",
  "cinematic",
];

type FeatureTab = "audio" | "voice" | "inspo" | null;
type DownloadKind = "lrc" | "srt" | "mp3" | "wav";

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

function clipVersionLabel(variant?: string | null): string {
  return variant === "alt" ? "Version 2" : "Version 1";
}

function generationClips(generation: WebMusicGeneration): WebMusicClip[] {
  if (generation.clips?.length) return generation.clips;
  return [
    {
      variant: "ok",
      label: generation.title,
      audio_url: "",
      download_url: "",
      ready: false,
    },
    {
      variant: "alt",
      label: generation.title,
      audio_url: "",
      download_url: "",
      ready: false,
    },
  ];
}

function clipTrackKey(songId: string, variant: string): string {
  return `${songId}:${variant}`;
}

function clipIsReady(generation: WebMusicGeneration, clip: WebMusicClip): boolean {
  return Boolean(clip.ready || clip.audio_url) ||
    String(generation.status).toLowerCase() === "success";
}

function generationIsInstrumental(generation: WebMusicGeneration): boolean {
  const lyrics = String(generation.lyrics || "").trim().toLowerCase();
  return Boolean(generation.instrumental) || !lyrics || lyrics === "[instrumental]";
}

function clipDownloadUrl(
  songId: string,
  variant: string,
  kind: DownloadKind
): string {
  const base = `/api/v3/web-music/generations/${encodeURIComponent(songId)}`;
  if (kind === "mp3") return `${base}/download?variant=${encodeURIComponent(variant)}`;
  if (kind === "wav") return `${base}/download-wav?variant=${encodeURIComponent(variant)}`;
  return `${base}/timed-lyrics?variant=${encodeURIComponent(variant)}&format=${kind}`;
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function percent(value?: number | null): string {
  return `${Math.round((value ?? 0.5) * 100)}%`;
}

function vocalLabel(value?: string | null): string {
  if (value === "f") return "Female";
  if (value === "m") return "Male";
  if (value === "both") return "Both";
  return "Not set";
}

function SelectBox({
  value,
  onChange,
  options,
  ariaLabel,
  className = "",
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  ariaLabel: string;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger
        aria-label={ariaLabel}
        className={cn("select-box", className)}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent className="create-select-content">
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function CreateStudio() {
  const { user, credits, loading, refresh } = useAuth();
  const { playTrack } = usePlayer();
  const [mode, setMode] = useState<Mode>("simple");
  const [prompt, setPrompt] = useState("");
  const [title, setTitle] = useState("");
  const [style, setStyle] = useState("");
  const [lyrics, setLyrics] = useState("");
  const [lyricsMode, setLyricsMode] = useState<LyricsMode>("write");
  const [instrumental, setInstrumental] = useState(false);
  const [model, setModel] = useState<WebMusicModel>("V6");
  const [vocalGender, setVocalGender] = useState<"f" | "m" | "both">("f");
  const [negativeTags, setNegativeTags] = useState("");
  const [styleWeight, setStyleWeight] = useState(0.5);
  const [weirdness, setWeirdness] = useState(0.5);
  const [audioWeight, setAudioWeight] = useState(0.5);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [featureTab, setFeatureTab] = useState<FeatureTab>(null);
  const [copied, setCopied] = useState<"style" | "lyrics" | null>(null);
  const [songs, setSongs] = useState<WebMusicGeneration[]>([]);
  const [loadingSongs, setLoadingSongs] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<WebMusicGeneration | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [writingLyrics, setWritingLyrics] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [quota, setQuota] = useState<WebMusicQuota | null>(null);
  const [workspaces, setWorkspaces] = useState<WebMusicWorkspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [workspacesReady, setWorkspacesReady] = useState(false);
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  const [newWorkspaceOpen, setNewWorkspaceOpen] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [renameWorkspaceOpen, setRenameWorkspaceOpen] = useState(false);
  const [renameWorkspaceName, setRenameWorkspaceName] = useState("");
  const [playlists, setPlaylists] = useState<WebMusicPlaylistSummary[]>([]);
  const [playlistOpen, setPlaylistOpen] = useState(false);
  const [playlistBusy, setPlaylistBusy] = useState(false);
  const [newPlaylistName, setNewPlaylistName] = useState("");
  const [totalSongs, setTotalSongs] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [simpleSongCount, setSimpleSongCount] = useState<number>(1);
  const [batchProgress, setBatchProgress] = useState<{ done: number; total: number } | null>(null);
  const [generatingStyles, setGeneratingStyles] = useState(false);
  const [stylesError, setStylesError] = useState("");
  const [selectedVariant, setSelectedVariant] = useState<string | null>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedClipKeys, setSelectedClipKeys] = useState<string[]>([]);
  const [batchFormat, setBatchFormat] = useState<DownloadKind>("mp3");
  const [batchDownloadProgress, setBatchDownloadProgress] = useState<{ done: number; total: number } | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchError, setBatchError] = useState("");
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const mounted = useRef(true);
  const cardBodyRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    cardBodyRef.current?.scrollTo({ top: 0 });
  }, [mode]);

  useEffect(() => {
    if (cooldownSeconds <= 0) return;
    const timer = window.setTimeout(() => {
      setCooldownSeconds((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [cooldownSeconds]);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      window.location.href = "/login?next=/create";
      return;
    }
    let active = true;
    Promise.all([
      listWebMusicWorkspaces().catch(() => ({ items: [] as WebMusicWorkspace[] })),
      fetchWebMusicQuota().catch(() => null),
    ])
      .then(([workspacePayload, quotaPayload]) => {
        if (!active) return;
        setWorkspaces(workspacePayload.items);
        setQuota(quotaPayload);
        const defaultWorkspace =
          workspacePayload.items.find((workspace) => workspace.is_default) ??
          workspacePayload.items[0] ??
          null;
        setActiveWorkspaceId(defaultWorkspace?.id ?? null);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Could not load your studio");
      })
      .finally(() => {
        if (active) setWorkspacesReady(true);
      });
    return () => {
      active = false;
    };
  }, [loading, user]);

  useEffect(() => {
    if (!workspacesReady || loading || !user) return;
    void reloadGenerations(activeWorkspaceId, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspacesReady, activeWorkspaceId, loading, user]);

  async function reloadGenerations(workspaceId: string | null, offset = 0) {
    if (offset === 0) setLoadingSongs(true);
    else setLoadingMore(true);
    try {
      const page = await listWebMusicGenerations(50, offset, workspaceId ?? undefined);
      if (!mounted.current) return;
      setSongs((current) => (offset === 0 ? page.items : [...current, ...page.items]));
      setTotalSongs(page.total);
      if (offset === 0) {
        const kept = selectedId ? page.items.find((item) => item.id === selectedId) : null;
        const next = kept ?? page.items[0] ?? null;
        if (next) {
          const variant =
            next.clips?.find((clip) => clip.variant === selectedVariant)?.variant ??
            next.clips?.[0]?.variant ??
            "ok";
          void loadDetail(next.id, variant);
        } else {
          setSelectedId(null);
          setSelectedDetail(null);
          setSelectedVariant(null);
        }
      }
    } catch (cause) {
      if (mounted.current) {
        setError(cause instanceof Error ? cause.message : "Could not load songs");
      }
    } finally {
      if (mounted.current) {
        setLoadingSongs(false);
        setLoadingMore(false);
      }
    }
  }

  async function loadDetail(id: string, variant?: string) {
    setSelectedId(id);
    setEditingTitle(false);
    if (variant) setSelectedVariant(variant);
    setDetailLoading(true);
    try {
      const detail = await getWebMusicGeneration(id);
      if (!mounted.current) return;
      setSelectedDetail(detail);
      const nextVariant =
        variant ??
        detail.clips?.find((clip) => clip.variant === selectedVariant)?.variant ??
        detail.clips?.[0]?.variant ??
        "ok";
      setSelectedVariant(nextVariant);
      setSongs((current) => current.map((item) => (item.id === detail.id ? detail : item)));
    } catch {
      if (mounted.current) setSelectedDetail(songs.find((item) => item.id === id) ?? null);
    } finally {
      if (mounted.current) setDetailLoading(false);
    }
  }

  async function selectSong(id: string, variant?: string) {
    await loadDetail(id, variant);
  }

  async function refreshSongs() {
    try {
      await reloadGenerations(activeWorkspaceId, 0);
      if (selectedId) {
        const detail = await getWebMusicGeneration(selectedId).catch(() => null);
        if (detail && mounted.current) setSelectedDetail(detail);
      }
      const nextQuota = await fetchWebMusicQuota().catch(() => null);
      if (nextQuota && mounted.current) setQuota(nextQuota);
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : "Could not refresh songs");
    }
  }

  const hasPending = songs.some((song) =>
    ["pending", "queued", "running"].includes(String(song.status).toLowerCase())
  );

  useEffect(() => {
    if (!hasPending) return;
    const timer = window.setInterval(() => {
      void refreshSongs();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [hasPending, selectedId]);

  const formReady =
    mode === "simple"
      ? prompt.trim().length > 0
      : instrumental
        ? style.trim().length > 0
        : style.trim().length > 0 && lyrics.trim().length > 0;

  async function writeLyrics() {
    const seed =
      (mode === "custom" && lyricsMode === "prompt" ? lyrics.trim() : prompt.trim()) ||
      title.trim() ||
      style.trim();
    if (!seed) {
      setError("Add a song description, title, or style first.");
      return;
    }
    setWritingLyrics(true);
    setError("");
    try {
      const draft = await generateWebMusicDraft(seed);
      setLyrics(draft.lyrics);
      if (!title.trim() && draft.title) setTitle(draft.title);
      setLyricsMode("write");
      const nextQuota = await fetchWebMusicQuota().catch(() => null);
      if (nextQuota && mounted.current) setQuota(nextQuota);
      void refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not write lyrics");
    } finally {
      setWritingLyrics(false);
    }
  }

  function appendStyle(chip: string) {
    setStyle((current) =>
      current.toLowerCase().includes(chip)
        ? current
        : [current.trim(), chip].filter(Boolean).join(", ").slice(0, 1000)
    );
  }

  function shuffleStyle() {
    const picks = [...styleChips].sort(() => Math.random() - 0.5).slice(0, 3);
    setStyle(picks.join(", "));
  }

  async function copyText(text: string, kind: "style" | "lyrics") {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      window.setTimeout(() => setCopied(null), 1600);
    } catch {
      setError("Copy failed. Select the text and copy it manually.");
    }
  }

  async function pollGeneration(id: string, attempts = 0) {
    if (!mounted.current) return;
    try {
      const generation = await getWebMusicGeneration(id);
      if (!mounted.current) return;
      setSongs((current) =>
        current.map((item) => (item.id === generation.id ? generation : item))
      );
      if (selectedId === generation.id) setSelectedDetail(generation);
      const done =
        String(generation.status).toLowerCase() === "success" ||
        (generation.clips?.some((clip) => clip.ready) ?? false);
      if (!done && attempts < 80) {
        window.setTimeout(() => void pollGeneration(id, attempts + 1), 3000);
      } else if (done) {
        setNotice("Your song is ready.");
        void refreshSongs();
        void refresh();
      }
    } catch {
      if (attempts < 30) {
        window.setTimeout(() => void pollGeneration(id, attempts + 1), 3000);
      }
    }
  }

  function playSong(song: WebMusicGeneration, preferredClip?: WebMusicClip) {
    const clip =
      preferredClip ??
      song.clips?.find((item) => item.ready && item.audio_url) ??
      song.clips?.find((item) => item.audio_url) ??
      song.clips?.[0];
    const variant = clip?.variant || "ok";
    const audioUrl =
      clip?.audio_url ||
      (String(song.status).toLowerCase() === "success"
        ? clip?.download_url ||
          `/api/v3/web-music/generations/${song.id}/stream/${variant}`
        : "");
    if (!audioUrl) return;
    playTrack({
      title: clip?.title || song.title || "Untitled",
      artist: "You",
      cover: clip?.image_url || "/hero.png",
      duration: Math.max(1, Math.round(clip?.duration_seconds || 180)),
      audioUrl,
    });
  }

  async function suggestStyles() {
    const hasContext = Boolean(style.trim() || lyrics.trim() || title.trim() || prompt.trim());
    if (!hasContext) {
      setStylesError("Add a style, title, lyrics, or song description first.");
      return;
    }
    setGeneratingStyles(true);
    setStylesError("");
    try {
      const result = await generateWebMusicStyles({
        style: style.trim(),
        lyrics: lyrics.trim(),
        title: title.trim(),
        description: prompt.trim(),
      });
      setStyle(result.style);
      const nextQuota = await fetchWebMusicQuota().catch(() => null);
      if (nextQuota && mounted.current) setQuota(nextQuota);
      void refresh();
    } catch (cause) {
      setStylesError(cause instanceof Error ? cause.message : "Style generation failed");
    } finally {
      if (mounted.current) setGeneratingStyles(false);
    }
  }

  async function onCreateWorkspace() {
    const name = newWorkspaceName.trim();
    if (!name || workspaceBusy) return;
    setWorkspaceBusy(true);
    setError("");
    try {
      const created = await createWebMusicWorkspace(name);
      setWorkspaces((current) => [...current, created]);
      setNewWorkspaceName("");
      setNewWorkspaceOpen(false);
      setActiveWorkspaceId(created.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create workspace");
    } finally {
      if (mounted.current) setWorkspaceBusy(false);
    }
  }

  async function onRenameWorkspace() {
    if (!activeWorkspaceId || workspaceBusy) return;
    const name = renameWorkspaceName.trim();
    if (!name) return;
    setWorkspaceBusy(true);
    setError("");
    try {
      const updated = await updateWebMusicWorkspace(activeWorkspaceId, name);
      setWorkspaces((current) =>
        current.map((workspace) => (workspace.id === updated.id ? updated : workspace))
      );
      setRenameWorkspaceOpen(false);
      setRenameWorkspaceName("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not rename workspace");
    } finally {
      if (mounted.current) setWorkspaceBusy(false);
    }
  }

  async function openPlaylistMenu() {
    setPlaylistOpen((value) => !value);
    if (!playlists.length) {
      const payload = await listWebMusicPlaylists().catch(() => ({ items: [] }));
      if (mounted.current) setPlaylists(payload.items);
    }
  }

  async function onAddToPlaylist(playlist: WebMusicPlaylistSummary) {
    if (!selected || !selectedClip?.ready || playlistBusy) {
      setError("This track upload is still processing. Try again once it is fully ready.");
      return;
    }
    setPlaylistBusy(true);
    setError("");
    try {
      await addWebMusicPlaylistItem(playlist.id, selected.id, selectedClip.variant);
      setNotice(`Added "${selectedClip.title || selected.title}" to ${playlist.name}.`);
      setPlaylistOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not add to playlist");
    } finally {
      if (mounted.current) setPlaylistBusy(false);
    }
  }

  async function onCreatePlaylist() {
    const name = newPlaylistName.trim();
    if (!name || playlistBusy) return;
    setPlaylistBusy(true);
    try {
      const created = await createWebMusicPlaylist(name);
      setPlaylists((current) => [...current, created]);
      setNewPlaylistName("");
      setNotice(`Created playlist "${created.name}".`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create playlist");
    } finally {
      if (mounted.current) setPlaylistBusy(false);
    }
  }

  async function loadMoreSongs() {
    if (loadingMore || songs.length >= totalSongs) return;
    await reloadGenerations(activeWorkspaceId, songs.length);
  }

  function toggleClipSelection(key: string) {
    setBatchError("");
    setSelectedClipKeys((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key]
    );
  }

  async function onBatchDownload() {
    if (!selectedClipKeys.length || batchBusy) return;
    const targets = songs
      .flatMap((song) =>
        generationClips(song).map((clip) => ({
          song,
          clip,
          key: clipTrackKey(song.id, clip.variant),
        }))
      )
      .filter(
        ({ song, clip, key }) =>
          selectedClipKeys.includes(key) &&
          clipIsReady(song, clip) &&
          !(generationIsInstrumental(song) && (batchFormat === "lrc" || batchFormat === "srt"))
      );
    if (!targets.length) {
      setBatchError("Select at least one ready track to download.");
      return;
    }
    setBatchBusy(true);
    setBatchError("");
    setBatchDownloadProgress({ done: 0, total: targets.length });
    try {
      const entries: ZipEntry[] = [];
      for (let index = 0; index < targets.length; index += 1) {
        const { song, clip } = targets[index];
        let blob: Blob;
        let extension = batchFormat;
        if (batchFormat === "mp3") {
          blob = await fetchWebMusicClipBlob(song.id, clip.variant);
        } else if (batchFormat === "wav") {
          blob = await fetchWebMusicClipWavBlob(song.id, clip.variant);
        } else {
          blob = await fetchWebMusicTimedLyricsBlob(song.id, clip.variant, batchFormat);
        }
        if (batchFormat === "lrc" || batchFormat === "srt") extension = batchFormat;
        entries.push({
          name: clipFilename(song, clip, extension),
          data: new Uint8Array(await blob.arrayBuffer()),
        });
        setBatchDownloadProgress({ done: index + 1, total: targets.length });
      }
      saveBlob(
        createStoreZip(entries),
        `camxora-${batchFormat}-${new Date().toISOString().slice(0, 10)}.zip`
      );
    } catch (cause) {
      setBatchError(cause instanceof Error ? cause.message : "Batch download failed");
    } finally {
      if (mounted.current) {
        setBatchBusy(false);
        setBatchDownloadProgress(null);
      }
    }
  }

  async function saveTitle() {
    if (!selected) return;
    const nextTitle = titleDraft.trim();
    if (!nextTitle) {
      setError("Title cannot be empty.");
      return;
    }
    try {
      const updated = await updateWebMusicGenerationTitle(
        selected.id,
        nextTitle,
        selectedClip?.variant
      );
      if (!mounted.current) return;
      setSelectedDetail(updated);
      setSongs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setEditingTitle(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not rename this track");
    }
  }

  async function deleteSelected() {
    if (!selected || deletingId) return;
    if (!window.confirm(`Delete "${selected.title}" permanently?`)) return;
    setDeletingId(selected.id);
    setError("");
    try {
      await deleteWebMusicGeneration(selected.id);
      if (!mounted.current) return;
      setSongs((current) => current.filter((item) => item.id !== selected.id));
      setTotalSongs((current) => Math.max(0, current - 1));
      setSelectedId(null);
      setSelectedDetail(null);
      setSelectedVariant(null);
      setSelectedClipKeys((current) => current.filter((key) => !key.startsWith(`${selected.id}:`)));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete this track");
    } finally {
      if (mounted.current) setDeletingId(null);
    }
  }

  async function unlockSelected() {
    if (!selected) return;
    setDetailLoading(true);
    try {
      const updated = await unlockWebMusicPreview(selected.id);
      if (!mounted.current) return;
      setSelectedDetail(updated);
      setSongs((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      void refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not unlock this preview");
    } finally {
      if (mounted.current) setDetailLoading(false);
    }
  }

  async function onSubmit() {
    if (busy || !formReady) return;
    if (cooldownSeconds > 0) {
      setError(`Please wait ${cooldownSeconds}s before creating another song.`);
      return;
    }
    if (queueFull) {
      setError(`The generation queue is full (${queueUsed}/${queueLimit}). Try again shortly.`);
      return;
    }
    if (batchRequiresUpgrade) {
      setError("Batch generation is a Pro feature. Upgrade or buy a credit pack to continue.");
      return;
    }
    if (quota?.requires_upgrade) {
      setError("A credit pack is required to generate full tracks. Open Buy packs to continue.");
      return;
    }
    setBusy(true);
    setError("");
    setStylesError("");
    setNotice("");
    let finalLyrics = lyrics.trim();
    if (mode === "custom" && !instrumental && lyricsMode === "prompt") {
      try {
        const draft = await generateWebMusicDraft(finalLyrics);
        finalLyrics = draft.lyrics;
        setLyrics(draft.lyrics);
        if (!title.trim() && draft.title) setTitle(draft.title);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Could not write lyrics");
        setBusy(false);
        return;
      }
    }
    const count = mode === "simple" ? simpleSongCount : 1;
    const payload: WebMusicGenerateInput = {
      mode: mode === "simple" ? "simple" : "advanced",
      prompt:
        mode === "simple"
          ? prompt.trim() || undefined
          : lyricsMode === "prompt"
            ? finalLyrics || undefined
            : undefined,
      title: title.trim() || undefined,
      style: mode === "custom" ? style.trim() || undefined : undefined,
      lyrics: mode === "custom" && !instrumental ? finalLyrics || undefined : undefined,
      instrumental,
      model,
      negative_tags: negativeTags.trim() || undefined,
      vocal_gender: instrumental ? undefined : vocalGender,
      style_weight: styleWeight,
      weirdness_constraint: weirdness,
      audio_weight: audioWeight,
      workspace_id: activeWorkspaceId ?? undefined,
    };
    setBatchProgress(count > 1 ? { done: 0, total: count } : null);
    let createdCount = 0;
    try {
      for (let index = 0; index < count; index += 1) {
        if (index > 0) {
          await new Promise((resolve) => window.setTimeout(resolve, BATCH_SUBMIT_GAP_MS));
        }
        const created = await generateWebMusic(payload);
        createdCount += 1;
        setQuota(created.quota);
        setBatchProgress({ done: createdCount, total: count });
        const loaded = await getWebMusicGeneration(created.task_id).catch(() => null);
        const pending: WebMusicGeneration = loaded ?? {
          id: created.task_id,
          title: created.title || title || "Untitled",
          lyrics: finalLyrics,
          style: created.style || style,
          model,
          model_label: created.model_label,
          is_preview: created.is_preview,
          unlockable: created.unlockable,
          preview_seconds: created.preview_seconds ?? null,
          instrumental,
          status: created.status || "pending",
          created_at: new Date().toISOString(),
          negative_tags: negativeTags || null,
          vocal_gender: instrumental ? null : vocalGender,
          style_weight: styleWeight,
          weirdness_constraint: weirdness,
          audio_weight: audioWeight,
          clips: [],
        };
        setSongs((current) => [pending, ...current.filter((item) => item.id !== pending.id)]);
        if (index === 0) {
          setSelectedId(pending.id);
          setSelectedDetail(pending);
          setSelectedVariant("ok");
        }
        void pollGeneration(created.task_id);
      }
      setNotice(
        count > 1
          ? `Queued ${count} songs. They will appear here as they finish.`
          : "Generation started. Your song will appear here."
      );
      setCooldownSeconds(5);
      void refreshSongs();
      void refresh();
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Could not start generation";
      const hint =
        cause instanceof WebMusicApiError && cause.status === 402
          ? " Open Buy packs to add credits."
          : "";
      setError(
        createdCount > 0
          ? `Created ${createdCount} of ${count} songs, then stopped: ${message}${hint}`
          : `${message}${hint}`
      );
      const nextQuota = await fetchWebMusicQuota().catch(() => null);
      if (nextQuota && mounted.current) setQuota(nextQuota);
    } finally {
      if (mounted.current) {
        setBusy(false);
        setBatchProgress(null);
      }
    }
  }

  const selected =
    selectedDetail?.id === selectedId
      ? selectedDetail
      : songs.find((song) => song.id === selectedId) ?? null;
  const selectedClip =
    selected?.clips?.find((clip) => clip.variant === selectedVariant) ??
    selected?.clips?.[0] ??
    null;
  const selectedCover = selectedClip?.image_url || "/hero.png";
  const selectedReady =
    selected && selectedClip
      ? clipIsReady(selected, selectedClip)
      : String(selected?.status || "").toLowerCase() === "success";
  const batchCount = mode === "simple" ? simpleSongCount : 1;
  const requiredCredits = (quota?.credits_per_song ?? 0) * batchCount;
  const availableCredits = quota?.credits_remaining ?? credits ?? 0;
  const needsCredits = requiredCredits > 0 && availableCredits < requiredCredits;
  const hasSubscription = Boolean(quota?.has_subscription || quota?.is_pro);
  const batchRequiresUpgrade = batchCount > 1 && !hasSubscription;
  const queueLimit = quota?.queue_limit ?? 20;
  const queueUsed = quota?.queue_used ?? 0;
  const queueSlotsFree = Math.max(0, queueLimit - queueUsed);
  const queueFull = queueUsed >= queueLimit;
  const batchOverQueue = batchCount > 1 && batchCount > queueSlotsFree;
  const createStatusHint = busy
    ? "Adding this song to the global queue. Paid songs go first."
    : cooldownSeconds > 0
      ? `You can create another in ${cooldownSeconds}s. No need to wait for audio.`
      : queueFull
        ? `Queue full (${queueUsed}/${queueLimit}). Wait until one song starts at Suno.`
        : queueUsed > 0
          ? `${queueUsed} in the global queue. Suno starts them one by one.`
          : null;
  const batchWarning =
    mode !== "simple" || batchCount <= 1
      ? null
      : batchRequiresUpgrade
        ? `Batch generation is a Pro feature. Upgrade to Pro or buy a credit pack to create ${batchCount} songs at once.`
        : needsCredits
          ? `You need ${requiredCredits.toLocaleString()} credits to create ${batchCount} songs but have ${availableCredits.toLocaleString()}. Top up or upgrade to continue.`
          : batchOverQueue
            ? `Only ${queueSlotsFree} of ${queueLimit} queue slots are free. Extra songs wait in the queue until earlier ones start at Suno.`
            : null;
  const activeWorkspaceName =
    workspaces.find((workspace) => workspace.id === activeWorkspaceId)?.name ?? "My Workspace";
  const generationCount = totalSongs || songs.length;
  const generationWord = generationCount === 1 ? "song" : "songs";
  const versionCount = songs.reduce((total, song) => total + generationClips(song).length, 0);
  const versionWord = versionCount === 1 ? "version" : "versions";
  const selectedInstrumental = selected ? generationIsInstrumental(selected) : false;
  const selectedClipAddable = Boolean(selectedClip?.ready);

  if (loading || !user) {
    return (
      <div className="page">
        <div className="page-head">
          <div>
            <div className="eyebrow">Studio</div>
            <h1>Create</h1>
            <p>{loading ? "Checking your session…" : "Redirecting to sign in…"}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page create-page">
      <div className="create-layout">
        <section className="panel create-card">
          <div className="create-card-top">
            <div className="create-tabs" role="tablist" aria-label="Creation mode">
              <button
                className={mode === "simple" ? "on" : ""}
                type="button"
                role="tab"
                aria-selected={mode === "simple"}
                onClick={() => setMode("simple")}
              >
                Simple
              </button>
              <button
                className={mode === "custom" ? "on" : ""}
                type="button"
                role="tab"
                aria-selected={mode === "custom"}
                onClick={() => setMode("custom")}
              >
                Advanced
              </button>
            </div>
            <div className="create-model-pill">
              <Icon name="fa-bolt" />
              <SelectBox
                value={model}
                onChange={(value) => setModel(value as WebMusicModel)}
                options={models}
                ariaLabel="Model"
                className="create-model-select"
              />
            </div>
          </div>

          <div className="create-feature-tabs">
            {(["audio", "voice", "inspo"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                className={featureTab === tab ? "on" : ""}
                aria-pressed={featureTab === tab}
                onClick={() => setFeatureTab((current) => (current === tab ? null : tab))}
              >
                + {tab}
              </button>
            ))}
          </div>
          {featureTab ? (
            <p className="create-feature-note">
              {featureTab === "audio"
                ? "Reference audio uploads are coming soon."
                : featureTab === "voice"
                  ? "Voice reference uploads are coming soon."
                  : "Inspiration references are coming soon."}
            </p>
          ) : null}

          <div className="create-card-body" ref={cardBodyRef}>
            {mode === "simple" ? (
              <div className="create-field">
                <div className="create-field-head">
                  <label htmlFor="create-prompt">Song description</label>
                  <span>{prompt.length}/5000</span>
                </div>
                <textarea
                  id="create-prompt"
                  className="textarea create-prompt"
                  placeholder="A warm Khmer ballad about the Mekong at sunset. Female vocal, acoustic guitar, 72 BPM…"
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  maxLength={5000}
                  rows={8}
                />
                <div className="create-count-card">
                  <div>
                    <b>Songs to generate</b>
                    <span>
                      Each song returns 2 versions
                      {requiredCredits > 0 ? ` · ${requiredCredits} credits total` : ""}
                    </span>
                  </div>
                  <SelectBox
                    value={String(simpleSongCount)}
                    onChange={(value) => setSimpleSongCount(Number(value))}
                    options={SIMPLE_SONG_COUNTS.map((count) => ({
                      value: String(count),
                      label:
                        count === 1
                          ? "1 song"
                          : `${count} songs · ${count * 2} versions`,
                    }))}
                    ariaLabel="Songs to generate"
                    className="create-count-select"
                  />
                </div>
                {batchWarning ? (
                  <p className="create-batch-warning" role="status">
                    {batchWarning} <Link href="/pricing">Upgrade</Link>
                  </p>
                ) : null}
              </div>
            ) : (
              <>
                <div className="create-section-head">
                  <h3>Lyrics</h3>
                  {lyricsMode === "write" ? (
                    <button
                      className="create-auto"
                      type="button"
                      onClick={writeLyrics}
                      disabled={writingLyrics || instrumental}
                    >
                      <Icon name="fa-wand-magic-sparkles" />
                      {writingLyrics ? "Generating…" : "Auto-generate"}
                    </button>
                  ) : (
                    <span className="create-auto-note">Generated on Create</span>
                  )}
                </div>
                <div className="create-lyrics-tabs" role="tablist" aria-label="Lyrics mode">
                  <button
                    className={lyricsMode === "write" ? "on" : ""}
                    type="button"
                    role="tab"
                    aria-selected={lyricsMode === "write"}
                    onClick={() => setLyricsMode("write")}
                  >
                    Write
                  </button>
                  <button
                    className={lyricsMode === "prompt" ? "on" : ""}
                    type="button"
                    role="tab"
                    aria-selected={lyricsMode === "prompt"}
                    onClick={() => setLyricsMode("prompt")}
                  >
                    Prompt
                  </button>
                </div>
                <textarea
                  className="textarea create-lyrics"
                  value={lyrics}
                  onChange={(event) => setLyrics(event.target.value)}
                  placeholder={
                    lyricsMode === "write"
                      ? "Write lyrics, or paste a verse…"
                      : "Describe the story or feeling you want the lyrics to capture…"
                  }
                  disabled={instrumental}
                  maxLength={5000}
                  rows={7}
                />
                <div className="create-char-row">
                  <span>{lyrics.length}/5000</span>
                </div>

                <div className="create-section-head">
                  <h3>Styles</h3>
                  <div className="create-style-actions">
                    <button className="create-shuffle" type="button" onClick={shuffleStyle}>
                      <Icon name="fa-shuffle" /> Shuffle
                    </button>
                    <button
                      className="create-enhance"
                      type="button"
                      onClick={() => void suggestStyles()}
                      disabled={generatingStyles}
                    >
                      <Icon name="fa-wand-magic-sparkles" />
                      {generatingStyles ? "Enhancing…" : "Enhance"}
                    </button>
                  </div>
                </div>
                <textarea
                  id="create-style"
                  className="textarea create-style"
                  value={style}
                  onChange={(event) => setStyle(event.target.value)}
                  placeholder="urbano, electric guitar, upbeat rock, 128 BPM, eurodance"
                  maxLength={1000}
                  rows={4}
                />
                <div className="create-chips">
                  {styleChips.map((chip) => (
                    <button key={chip} type="button" onClick={() => appendStyle(chip)}>
                      {chip}
                    </button>
                  ))}
                </div>
                {stylesError ? <p className="create-section-error" role="alert">{stylesError}</p> : null}
                <div className="create-field create-negative">
                  <label htmlFor="create-negative">Negative tags (optional)</label>
                  <input
                    id="create-negative"
                    className="input"
                    value={negativeTags}
                    onChange={(event) => setNegativeTags(event.target.value)}
                    placeholder="choir, backing vocals, falsetto"
                  />
                </div>
              </>
            )}

            <div className="create-option-card">
              <div>
                <b>Instrumental</b>
                <span>No vocals — music only.</span>
              </div>
              <Switch
                checked={instrumental}
                onCheckedChange={setInstrumental}
                aria-label="Instrumental"
              />
            </div>

            <button
              className="create-advanced-toggle"
              type="button"
              aria-expanded={advancedOpen}
              onClick={() => setAdvancedOpen((value) => !value)}
            >
              <Icon name="fa-sliders" />
              More Options
              <Icon name={advancedOpen ? "fa-chevron-up" : "fa-chevron-down"} />
            </button>

            {advancedOpen ? (
              <div className="create-advanced">
                <div className="create-field">
                  <label>Vocal gender</label>
                  <SelectBox
                    value={vocalGender}
                    onChange={(value) => setVocalGender(value as "f" | "m" | "both")}
                    options={[
                      { value: "f", label: "Female" },
                      { value: "m", label: "Male" },
                      { value: "both", label: "Both" },
                    ]}
                    ariaLabel="Vocal gender"
                    className="create-select-full"
                  />
                </div>
                <div className="create-sliders">
                  <label>Style influence <b>{Math.round(styleWeight * 100)}%</b><input type="range" min="0" max="1" step="0.01" value={styleWeight} onChange={(event) => setStyleWeight(Number(event.target.value))} /></label>
                  <label>Weirdness <b>{Math.round(weirdness * 100)}%</b><input type="range" min="0" max="1" step="0.01" value={weirdness} onChange={(event) => setWeirdness(Number(event.target.value))} /></label>
                  <label>Audio influence <b>{Math.round(audioWeight * 100)}%</b><input type="range" min="0" max="1" step="0.01" value={audioWeight} onChange={(event) => setAudioWeight(Number(event.target.value))} /></label>
                </div>
              </div>
            ) : null}

            <label className="create-title-row" htmlFor="create-title">
              <Icon name="fa-music" />
              <span className="create-title-label">Song title</span>
              <input
                id="create-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Optional"
                maxLength={200}
                aria-label="Song title (optional)"
              />
            </label>

            {error ? <p className="fine create-error" role="alert">{error}</p> : null}
            {notice ? <p className="fine create-notice" role="status">{notice}</p> : null}
          </div>

          <div className="create-submit">
            <span className="create-cost">
              <Icon name="fa-coins" />
              {requiredCredits > 0
                ? `${requiredCredits.toLocaleString()} credits · ${availableCredits.toLocaleString()} available`
                : "Uses your credit balance"}
            </span>
            {(needsCredits && batchCount === 1) || quota?.requires_upgrade ? (
              <p className="create-credit-warning">
                Not enough credits for this selection.{" "}
                <Link href="/pricing">Buy packs</Link>
              </p>
            ) : null}
            {createStatusHint ? (
              <p className="create-status-hint" role="status">{createStatusHint}</p>
            ) : null}
            <button
              className="create-generate-btn"
              type="button"
              onClick={onSubmit}
              disabled={busy || !formReady || needsCredits || batchRequiresUpgrade || queueFull || cooldownSeconds > 0 || Boolean(quota?.requires_upgrade)}
              aria-busy={busy}
            >
              <Icon name="fa-music" />{" "}
              {batchProgress
                ? `Creating ${Math.min(batchProgress.done + 1, batchProgress.total)}/${batchProgress.total}…`
                : busy
                  ? "Creating…"
                  : cooldownSeconds > 0
                    ? `Wait ${cooldownSeconds}s`
                    : queueFull
                      ? `Queue full (${queueUsed}/${queueLimit})`
                      : mode === "simple" && simpleSongCount > 1
                        ? `Create ${simpleSongCount} songs${requiredCredits > 0 ? ` · ${requiredCredits} credits` : ""}`
                        : requiredCredits > 0
                          ? `Create · ${requiredCredits} credits`
                          : "Create"}
            </button>
          </div>
        </section>

        <section className="panel create-workspace" aria-busy={loadingSongs}>
          <div className="create-workspace-head">
            <div className="create-workspace-title-block">
              <p className="create-eyebrow">Workspaces</p>
              <div className="create-workspace-title-row">
                <SelectBox
                  value={activeWorkspaceId ?? workspaces[0]?.id ?? "default"}
                  onChange={(value) => {
                    setActiveWorkspaceId(value === "default" ? null : value);
                    setSelectedClipKeys([]);
                  }}
                  options={
                    workspaces.length
                      ? workspaces.map((workspace) => ({
                          value: workspace.id,
                          label: workspace.name,
                        }))
                      : [{ value: "default", label: "My Workspace" }]
                  }
                  ariaLabel="Workspace"
                  className="create-workspace-select"
                />
                <button
                  className="create-new-workspace-btn"
                  type="button"
                  onClick={() => {
                    setRenameWorkspaceOpen((value) => !value);
                    setRenameWorkspaceName(activeWorkspaceName);
                    setNewWorkspaceOpen(false);
                  }}
                  aria-label="Rename workspace"
                  title="Rename workspace"
                >
                  <Icon name="fa-pen" />
                </button>
                <button
                  className="create-new-workspace-btn"
                  type="button"
                  onClick={() => {
                    setNewWorkspaceOpen((value) => !value);
                    setRenameWorkspaceOpen(false);
                  }}
                  aria-label="New workspace"
                  title="New workspace"
                >
                  <Icon name="fa-plus" />
                </button>
              </div>
              {renameWorkspaceOpen ? (
                <div className="create-new-workspace">
                  <input
                    autoFocus
                    value={renameWorkspaceName}
                    onChange={(event) => setRenameWorkspaceName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void onRenameWorkspace();
                      if (event.key === "Escape") setRenameWorkspaceOpen(false);
                    }}
                    placeholder="Workspace name"
                    aria-label="Workspace name"
                    maxLength={120}
                  />
                  <button type="button" onClick={() => void onRenameWorkspace()} disabled={workspaceBusy || !renameWorkspaceName.trim()}>
                    {workspaceBusy ? "Saving…" : "Save"}
                  </button>
                  <button type="button" onClick={() => setRenameWorkspaceOpen(false)}>Cancel</button>
                </div>
              ) : null}
              {newWorkspaceOpen ? (
                <div className="create-new-workspace">
                  <input
                    autoFocus
                    value={newWorkspaceName}
                    onChange={(event) => setNewWorkspaceName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void onCreateWorkspace();
                      if (event.key === "Escape") setNewWorkspaceOpen(false);
                    }}
                    placeholder="Workspace name"
                    aria-label="New workspace name"
                    maxLength={120}
                  />
                  <button type="button" onClick={() => void onCreateWorkspace()} disabled={workspaceBusy || !newWorkspaceName.trim()}>
                    {workspaceBusy ? "Saving…" : "Create"}
                  </button>
                  <button type="button" onClick={() => setNewWorkspaceOpen(false)}>Cancel</button>
                </div>
              ) : null}
            </div>
            <div className="create-workspace-actions">
              <span className="create-song-count">{generationCount} {generationWord}</span>
              <button type="button" onClick={() => void refreshSongs()} aria-label="Refresh songs">
                <Icon name="fa-rotate" />
              </button>
              <Link href="/library">Library</Link>
            </div>
          </div>
          <div className="create-workspace-toolbar">
            <label className="create-select-mode">
              <Checkbox
                checked={selectionMode}
                onCheckedChange={(checked) => {
                  const next = checked === true;
                  setSelectionMode(next);
                  setBatchError("");
                  if (!next) setSelectedClipKeys([]);
                }}
                aria-label="Select tracks"
              />
              <span>Select</span>
            </label>
            {selectionMode ? (
              <div className="create-batch-actions">
                <span role="status" aria-live="polite">{selectedClipKeys.length} selected</span>
                <SelectBox
                  value={batchFormat}
                  onChange={(value) => {
                    setBatchFormat(value as DownloadKind);
                    setBatchError("");
                  }}
                  options={DOWNLOAD_FORMATS}
                  ariaLabel="Batch download format"
                  className="create-batch-format"
                />
                <button
                  type="button"
                  onClick={() => void onBatchDownload()}
                  disabled={batchBusy || selectedClipKeys.length === 0}
                  aria-busy={batchBusy}
                  title={`Download selected as ${batchFormat.toUpperCase()} ZIP`}
                >
                  <Icon name="fa-download" />
                  {batchBusy
                    ? batchDownloadProgress
                      ? `${batchDownloadProgress.done}/${batchDownloadProgress.total}`
                      : "Preparing…"
                    : "ZIP"}
                </button>
                <button type="button" onClick={() => setSelectedClipKeys([])}>Clear</button>
              </div>
            ) : (
              <>
                <span><Icon name="fa-layer-group" /> All generations</span>
                <span>{loadingSongs ? "Loading…" : "Newest first"}</span>
              </>
            )}
          </div>
          {batchError ? <p className="create-batch-error" role="alert">{batchError}</p> : null}
          {loadingSongs ? (
            <div className="create-skeleton-list" role="status" aria-label="Loading your songs">
              {[0, 1, 2].map((item) => (
                <div className="create-skeleton-row" key={item}>
                  <span className="create-skeleton-cover" />
                  <span className="create-skeleton-copy">
                    <span />
                    <span />
                  </span>
                </div>
              ))}
            </div>
          ) : !songs.length ? (
            <div className="create-empty">
              <span><Icon name="fa-music" /></span>
              <h3>Your songs will land here</h3>
              <p>Write a description or lyrics, then hit Create.</p>
            </div>
          ) : (
            <div className="create-song-list">
              {songs.flatMap((song) =>
                generationClips(song).map((clip) => {
                  const ready = clipIsReady(song, clip);
                  const key = clipTrackKey(song.id, clip.variant);
                  const isSelected = selectedId === song.id && selectedVariant === clip.variant;
                  const title = clip.title || song.title || "Untitled";
                  return (
                    <div
                      className={`create-song${isSelected ? " selected" : ""}`}
                      key={key}
                      onClick={() => void selectSong(song.id, clip.variant)}
                    >
                      {selectionMode ? (
                        <label
                          className="create-clip-check-wrap"
                          onClick={(event) => event.stopPropagation()}
                          title={ready ? `Select ${title}` : "Not ready"}
                        >
                          <Checkbox
                            checked={selectedClipKeys.includes(key)}
                            disabled={!ready}
                            aria-label={`Select ${title} ${clipVersionLabel(clip.variant)}`}
                            onCheckedChange={() => toggleClipSelection(key)}
                          />
                        </label>
                      ) : null}
                      <button
                        className={`create-song-cover${ready ? "" : " pending"}`}
                        type="button"
                        aria-label={ready ? `Play ${title}` : "Song not ready"}
                        onClick={(event) => {
                          event.stopPropagation();
                          if (ready) playSong(song, clip);
                        }}
                        disabled={!ready}
                      >
                        <img src={clip.image_url || "/hero.png"} alt="" loading="lazy" />
                        <span><Icon name={ready ? "fa-play" : "fa-clock"} /></span>
                      </button>
                      <button
                        className="create-song-info"
                        type="button"
                        aria-pressed={isSelected}
                        aria-label={`Select ${title} ${clipVersionLabel(clip.variant)}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          void selectSong(song.id, clip.variant);
                        }}
                      >
                        <span className="create-song-title">
                          <b>{title}</b>
                          <em>{clipVersionLabel(clip.variant)}</em>
                        </span>
                        <span className="create-song-meta">
                          <i className={ready ? "ready" : ""}>{ready ? "Ready" : statusLabel(song.status)}</i>
                          {" · "}
                          {song.model_label || song.model || "V6"}
                          {" · "}
                          {formatDate(song.created_at)}
                        </span>
                      </button>
                      <div className="create-song-actions" onClick={(event) => event.stopPropagation()}>
                        {ready ? (
                          <>
                            {!generationIsInstrumental(song) ? (
                              <>
                                <a href={clipDownloadUrl(song.id, clip.variant, "lrc")} title="Download LRC">LRC</a>
                                <a href={clipDownloadUrl(song.id, clip.variant, "srt")} title="Download SRT">SRT</a>
                              </>
                            ) : null}
                            <a href={clip.download_url || clipDownloadUrl(song.id, clip.variant, "mp3")} title="Download MP3">MP3</a>
                            <a href={clipDownloadUrl(song.id, clip.variant, "wav")} title="Download WAV">WAV</a>
                          </>
                        ) : (
                          <span className="create-song-waiting">Waiting</span>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
          {songs.length ? (
            songs.length < totalSongs ? (
              <button className="create-load-more" type="button" onClick={() => void loadMoreSongs()} disabled={loadingMore}>
                {loadingMore ? "Loading…" : `Load more (${songs.length} of ${totalSongs})`}
              </button>
            ) : (
              <p className="create-list-foot">
                Showing all {generationCount} {generationWord} · {versionCount} {versionWord}
              </p>
            )
          ) : null}
        </section>

        <aside className="panel create-inspector" aria-busy={detailLoading}>
          {!selected ? (
            <div className="create-inspector-empty">
              <Icon name="fa-circle-info" />
              <p>Select a track to see its settings, style, and lyrics.</p>
            </div>
          ) : detailLoading ? (
            <div className="create-inspector-loading" role="status" aria-live="polite">
              <span className="create-loading-spinner" aria-hidden="true" />
              <b>Loading track details…</b>
              <span>Fetching lyrics, style, and settings.</span>
            </div>
          ) : (
            <>
              <div className="create-detail-head">
                <img src={selectedCover} alt="" />
                <div>
                  {editingTitle ? (
                    <div className="create-title-editor">
                      <input
                        autoFocus
                        value={titleDraft}
                        onChange={(event) => setTitleDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") void saveTitle();
                          if (event.key === "Escape") setEditingTitle(false);
                        }}
                        maxLength={200}
                        aria-label="Track title"
                      />
                      <button type="button" onClick={() => void saveTitle()} aria-label="Save title">
                        <Icon name="fa-check" />
                      </button>
                      <button type="button" onClick={() => setEditingTitle(false)} aria-label="Cancel title edit">
                        <Icon name="fa-xmark" />
                      </button>
                    </div>
                  ) : (
                    <div className="create-detail-title">
                      <h3>{selectedClip?.title || selected.title || "Untitled"}</h3>
                      <em>{clipVersionLabel(selectedClip?.variant)}</em>
                      <button
                        className="create-edit-title"
                        type="button"
                        onClick={() => {
                          setTitleDraft(selectedClip?.title || selected.title || "");
                          setEditingTitle(true);
                        }}
                        aria-label="Rename track"
                        title="Rename track"
                      >
                        <Icon name="fa-pen" />
                      </button>
                    </div>
                  )}
                  <span className="create-detail-sub">
                    <i className={selectedReady ? "ready" : ""}>{selectedReady ? "Ready" : statusLabel(selected.status)}</i>
                    {" · "}
                    {selected.model_label || selected.model || "V6"}
                    {" · "}
                    {formatDate(selected.created_at)}
                  </span>
                </div>
              </div>

              <div className="create-detail-actions">
                <button
                  className="create-action create-action-play"
                  type="button"
                  onClick={() => playSong(selected, selectedClip ?? undefined)}
                  disabled={!selectedReady}
                  aria-label="Play track"
                >
                  <Icon name="fa-play" /> Play
                </button>
                {selected.unlockable ? (
                  <button
                    className="create-action create-action-unlock"
                    type="button"
                    onClick={() => void unlockSelected()}
                    disabled={detailLoading}
                  >
                    <Icon name="fa-lock-open" /> Unlock
                  </button>
                ) : null}
                {selectedReady && selectedClip ? (
                  <>
                    {!selectedInstrumental ? (
                      <>
                        <a className="create-action" href={clipDownloadUrl(selected.id, selectedClip.variant || "ok", "lrc")} title="Download LRC">LRC</a>
                        <a className="create-action" href={clipDownloadUrl(selected.id, selectedClip.variant || "ok", "srt")} title="Download SRT">SRT</a>
                      </>
                    ) : null}
                    <a className="create-action" href={selectedClip.download_url || clipDownloadUrl(selected.id, selectedClip.variant || "ok", "mp3")} title="Download MP3">MP3</a>
                    <a className="create-action" href={clipDownloadUrl(selected.id, selectedClip.variant || "ok", "wav")} title="Download WAV">WAV</a>
                  </>
                ) : null}
                <button
                  className="create-action"
                  type="button"
                  onClick={() => void openPlaylistMenu()}
                  disabled={!selectedReady || !selectedClip || !selectedClipAddable || playlistBusy}
                  title={selectedClipAddable ? "Add to playlist" : "Playlist is available after the track upload completes"}
                >
                  <Icon name="fa-list" /> Playlist
                </button>
              </div>

              {playlistOpen ? (
                <div className="create-playlist-menu">
                  <div className="create-playlist-menu-head">
                    <span>Add to playlist</span>
                    <button type="button" onClick={() => setPlaylistOpen(false)} aria-label="Close playlist menu">
                      <Icon name="fa-xmark" />
                    </button>
                  </div>
                  <div className="create-playlist-list">
                    {playlists.length ? playlists.map((playlist) => (
                      <button
                        key={playlist.id}
                        type="button"
                        onClick={() => void onAddToPlaylist(playlist)}
                        disabled={playlistBusy}
                      >
                        <Icon name="fa-music" />
                        <span>{playlist.name}</span>
                        <small>{playlist.song_count ?? 0}</small>
                      </button>
                    )) : (
                      <p>No playlists yet. Create one below.</p>
                    )}
                  </div>
                  <div className="create-playlist-create">
                    <input
                      value={newPlaylistName}
                      onChange={(event) => setNewPlaylistName(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") void onCreatePlaylist();
                      }}
                      placeholder="New playlist"
                      aria-label="New playlist name"
                      maxLength={120}
                    />
                    <button type="button" onClick={() => void onCreatePlaylist()} disabled={playlistBusy || !newPlaylistName.trim()}>
                      <Icon name="fa-plus" />
                    </button>
                  </div>
                </div>
              ) : null}

              <div className="create-detail-section">
                <div className="create-detail-label">Settings</div>
                <div className="create-settings">
                  <div><span>Model</span><b>{selected.model_label || selected.model || "V6"}</b></div>
                  <div><span>Type</span><b>{selectedInstrumental ? "Instrumental" : "With Vocals"}</b></div>
                  <div><span>Vocal Gender</span><b>{selectedInstrumental ? "Not set" : vocalLabel(selected.vocal_gender)}</b></div>
                  <div><span>Style Influence</span><b>{percent(selected.style_weight)}</b></div>
                  <div><span>Weirdness</span><b>{percent(selected.weirdness_constraint)}</b></div>
                  <div><span>Audio Weight</span><b>{percent(selected.audio_weight)}</b></div>
                  <div><span>Status</span><b>{selectedReady ? "Ready" : statusLabel(selected.status)}</b></div>
                </div>
              </div>

              {selected.negative_tags ? (
                <div className="create-detail-section">
                  <div className="create-detail-label">Negative Tags</div>
                  <div className="create-detail-box">{selected.negative_tags}</div>
                </div>
              ) : null}

              <div className="create-detail-section">
                <div className="create-detail-label-row">
                  <span className="create-detail-label">Style</span>
                  <button type="button" className="create-copy" onClick={() => void copyText(selected.style || "", "style")} aria-label="Copy style">
                    <Icon name={copied === "style" ? "fa-check" : "fa-copy"} />
                  </button>
                </div>
                <div className="create-detail-box">{selected.style || "—"}</div>
              </div>

              <div className="create-detail-section">
                <div className="create-detail-label-row">
                  <span className="create-detail-label">Lyrics</span>
                  <button type="button" className="create-copy" onClick={() => void copyText(selected.lyrics || "", "lyrics")} aria-label="Copy lyrics">
                    <Icon name={copied === "lyrics" ? "fa-check" : "fa-copy"} />
                  </button>
                </div>
                <pre className="create-detail-lyrics">{selectedInstrumental ? "Instrumental — no lyrics" : selected.lyrics || "No lyrics saved."}</pre>
              </div>

              <div className="create-detail-footer">
                <Link className="create-open-studio" href="/studio/editor">
                  <Icon name="fa-table-columns" /> Open in Studio
                </Link>
                <button
                  className="create-delete"
                  type="button"
                  onClick={() => void deleteSelected()}
                  disabled={deletingId === selected.id}
                >
                  <Icon name="fa-trash" /> {deletingId === selected.id ? "Deleting…" : "Delete"}
                </button>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
