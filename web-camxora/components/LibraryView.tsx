"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Icon } from "@/components/Icon";
import { TrackRail } from "@/components/TrackRail";
import { useAuth } from "@/components/AuthProvider";
import { usePlayer } from "@/components/PlayerProvider";
import {
  fetchLikedTracks,
  type LikedTrack,
  type WebMusicClip,
  type WebMusicGeneration,
} from "@/lib/library-api";
import {
  addWebMusicPlaylistItem,
  createWebMusicPlaylist,
  createWebMusicWorkspace,
  deleteWebMusicGeneration,
  deleteWebMusicPlaylist,
  fetchWebMusicLikedKeys,
  getWebMusicGeneration,
  likeWebMusicGeneration,
  listWebMusicGenerations,
  listWebMusicPlaylistItems,
  listWebMusicPlaylists,
  listWebMusicStudioProjects,
  listWebMusicWorkspaces,
  unlockWebMusicPreview,
  updateWebMusicGenerationTitle,
  type WebMusicPlaylistItem,
  type WebMusicPlaylistSummary,
  type WebMusicStudioProject,
  type WebMusicWorkspace,
} from "@/lib/web-music-api";
import {
  clipDownloadUrl,
  clipIsReady,
  clipTrackKey,
  clipVersionLabel,
  formatClipDuration,
  formatDate,
  generationClips,
  generationIsInstrumental,
  statusClass,
  statusLabel,
  type ClipDownloadKind,
} from "@/lib/clip-utils";

const PAGE_SIZE = 50;

const TABS = [
  { id: "songs", label: "Songs" },
  { id: "playlists", label: "Playlists" },
  { id: "albums", label: "Albums" },
  { id: "workspaces", label: "Workspaces" },
  { id: "projects", label: "Studio Projects" },
  { id: "covers", label: "Cover Art" },
  { id: "hooks", label: "Hooks" },
  { id: "likedHooks", label: "Liked Hooks" },
  { id: "history", label: "History" },
] as const;

type LibTab = (typeof TABS)[number]["id"];

type FeedSort = "new" | "old" | "most" | "least";

type FeedFilter =
  | "liked"
  | "disliked"
  | "public"
  | "private"
  | "uploads"
  | "full"
  | "cover"
  | "voice"
  | "downloads"
  | "hideDisliked"
  | "hideStems";

type LibRow = {
  song: WebMusicGeneration;
  clip: WebMusicClip;
  key: string;
  title: string;
  ready: boolean;
  duration: number;
  createdAt: number;
  liked: boolean;
  disliked: boolean;
};

type ConfirmState =
  | { kind: "generations"; ids: string[] }
  | { kind: "playlist"; playlist: WebMusicPlaylistSummary }
  | null;

const filterOptions: Array<{ id: FeedFilter; label: string; disabled?: boolean }> = [
  { id: "liked", label: "Liked" },
  { id: "disliked", label: "Disliked" },
  { id: "public", label: "Public", disabled: true },
  { id: "private", label: "Private", disabled: true },
  { id: "uploads", label: "Uploads", disabled: true },
  { id: "full", label: "Full song" },
  { id: "cover", label: "Cover", disabled: true },
  { id: "voice", label: "Voice", disabled: true },
  { id: "downloads", label: "Downloads" },
  { id: "hideDisliked", label: "Hide Disliked" },
  { id: "hideStems", label: "Hide Stems", disabled: true },
];

const SORT_OPTIONS: Array<{ id: FeedSort; label: string }> = [
  { id: "new", label: "Newest" },
  { id: "old", label: "Oldest" },
  { id: "most", label: "Most liked" },
  { id: "least", label: "Least liked" },
];

const DOWNLOAD_KINDS: Array<{ kind: ClipDownloadKind; label: string }> = [
  { kind: "mp3", label: "Download MP3" },
  { kind: "wav", label: "Download WAV" },
  { kind: "lrc", label: "Download LRC" },
  { kind: "srt", label: "Download SRT" },
];

function errorText(result: PromiseSettledResult<unknown>, fallback: string): string {
  return result.status === "rejected" && result.reason instanceof Error
    ? result.reason.message
    : fallback;
}

export function LibraryView() {
  const { user, loading: authLoading } = useAuth();
  const { playTrack } = usePlayer();
  const mounted = useRef(true);

  const [tab, setTab] = useState<LibTab>("songs");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<FeedFilter[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [sort, setSort] = useState<FeedSort>("new");
  const [sortOpen, setSortOpen] = useState(false);
  const [page, setPage] = useState(1);

  const [bootLoading, setBootLoading] = useState(true);
  const [loadingGenerations, setLoadingGenerations] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  const [generations, setGenerations] = useState<WebMusicGeneration[]>([]);
  const [totalGenerations, setTotalGenerations] = useState(0);
  const [playlists, setPlaylists] = useState<WebMusicPlaylistSummary[]>([]);
  const [workspaces, setWorkspaces] = useState<WebMusicWorkspace[]>([]);
  const [projects, setProjects] = useState<WebMusicStudioProject[]>([]);
  const [likedTracks, setLikedTracks] = useState<LikedTrack[]>([]);
  const [likedKeys, setLikedKeys] = useState<string[]>([]);
  const [dislikedKeys, setDislikedKeys] = useState<string[]>([]);

  const [audioMenuOpen, setAudioMenuOpen] = useState(false);
  const [rowMenuKey, setRowMenuKey] = useState<string | null>(null);
  const [trashMode, setTrashMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [attachNotice, setAttachNotice] = useState<null | "upload" | "record">(null);

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WebMusicGeneration | null>(null);
  const [detailVariant, setDetailVariant] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [playlistDetail, setPlaylistDetail] = useState<WebMusicPlaylistSummary | null>(null);
  const [playlistItems, setPlaylistItems] = useState<WebMusicPlaylistItem[]>([]);
  const [playlistItemsLoading, setPlaylistItemsLoading] = useState(false);
  const [playlistError, setPlaylistError] = useState("");

  const [composer, setComposer] = useState<null | "playlist" | "workspace">(null);
  const [composerName, setComposerName] = useState("");
  const [composerBusy, setComposerBusy] = useState(false);

  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const [deleting, setDeleting] = useState(false);
  const [toast, setToast] = useState("");

  const tabListRef = useRef<HTMLDivElement | null>(null);
  const [indicator, setIndicator] = useState({ left: 0, width: 0 });
  const [tabsOverflow, setTabsOverflow] = useState(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      window.location.href = "/login?next=/library";
      return;
    }
    let active = true;
    setBootLoading(true);
    setLoadingGenerations(true);
    setError("");
    void (async () => {
      const [gens, pls, wss, prjs, liked, keys] = await Promise.allSettled([
        listWebMusicGenerations(PAGE_SIZE, 0),
        listWebMusicPlaylists(),
        listWebMusicWorkspaces(),
        listWebMusicStudioProjects(),
        fetchLikedTracks(50),
        fetchWebMusicLikedKeys(),
      ] as const);
      if (!active) return;
      const problems: string[] = [];

      if (gens.status === "fulfilled") {
        setGenerations(gens.value.items);
        setTotalGenerations(gens.value.total);
      } else {
        problems.push(errorText(gens, "Could not load your songs"));
      }
      if (pls.status === "fulfilled") setPlaylists(pls.value.items);
      else problems.push(errorText(pls, "Could not load your playlists"));
      if (wss.status === "fulfilled") setWorkspaces(wss.value.items);
      else problems.push(errorText(wss, "Could not load your workspaces"));
      if (prjs.status === "fulfilled") setProjects(prjs.value.items);
      else problems.push(errorText(prjs, "Could not load studio projects"));
      if (liked.status === "fulfilled") setLikedTracks(liked.value);
      else problems.push(errorText(liked, "Could not load liked tracks"));
      if (keys.status === "fulfilled") setLikedKeys(keys.value);
      else problems.push(errorText(keys, "Could not load your likes"));

      if (problems.length) setError(problems[0]);
      setBootLoading(false);
      setLoadingGenerations(false);
    })();
    return () => {
      active = false;
    };
  }, [authLoading, user]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 2400);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    setPage(1);
  }, [tab, search, filters, sort]);

  useEffect(() => {
    const measure = () => {
      const list = tabListRef.current;
      if (!list) return;
      const active = list.querySelector<HTMLElement>('[aria-selected="true"]');
      if (!active) return;
      setIndicator({ left: active.offsetLeft, width: active.offsetWidth });
      setTabsOverflow(list.scrollWidth > list.clientWidth + 1);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [tab, authLoading, bootLoading, detailOpen]);

  useEffect(() => {
    const onDoc = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("[data-s-menu]")) return;
      setFiltersOpen(false);
      setSortOpen(false);
      setAudioMenuOpen(false);
      setRowMenuKey(null);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setFiltersOpen(false);
      setSortOpen(false);
      setAudioMenuOpen(false);
      setRowMenuKey(null);
      closeDetail();
      setAttachNotice(null);
      setComposer(null);
      setConfirm(null);
      setPlaylistDetail(null);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    if (bootLoading || !user) return;
    const params = new URLSearchParams(window.location.search);
    const clipId = params.get("clip");
    if (!clipId) return;
    const variant = params.get("variant") || undefined;
    void openDetailById(clipId, variant);
    // Deep link is only read once per load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bootLoading, user]);

  async function loadGenerations(offset = 0) {
    if (offset === 0) setLoadingGenerations(true);
    else setLoadingMore(true);
    try {
      const pageData = await listWebMusicGenerations(PAGE_SIZE, offset);
      if (!mounted.current) return;
      setGenerations((current) => {
        if (offset === 0) return pageData.items;
        const seen = new Set(current.map((item) => item.id));
        return [...current, ...pageData.items.filter((item) => !seen.has(item.id))];
      });
      setTotalGenerations(pageData.total);
    } catch (cause) {
      if (mounted.current) {
        setError(cause instanceof Error ? cause.message : "Could not load your songs");
      }
    } finally {
      if (mounted.current) {
        setLoadingGenerations(false);
        setLoadingMore(false);
      }
    }
  }

  const isLikedRow = (song: WebMusicGeneration, clip: WebMusicClip) =>
    likedKeys.includes(clipTrackKey(song.id, clip.variant));
  const isDislikedRow = (song: WebMusicGeneration, clip: WebMusicClip) =>
    dislikedKeys.includes(clipTrackKey(song.id, clip.variant));

  const allRows: LibRow[] = generations.flatMap((song) =>
    generationClips(song).map((clip) => ({
      song,
      clip,
      key: clipTrackKey(song.id, clip.variant),
      title: clip.title || song.title || "Untitled",
      ready: clipIsReady(song, clip),
      duration: Math.round(clip.duration_seconds || 0),
      createdAt: song.created_at ? new Date(song.created_at).getTime() : 0,
      liked: isLikedRow(song, clip),
      disliked: isDislikedRow(song, clip),
    }))
  );

  const searchTerm = search.trim().toLowerCase();

  const filteredRows = allRows.filter((row) => {
    if (searchTerm) {
      const haystack =
        `${row.title} ${row.song.style || ""} ${row.song.lyrics || ""}`.toLowerCase();
      if (!haystack.includes(searchTerm)) return false;
    }
    if (filters.includes("liked") && !row.liked) return false;
    if (filters.includes("disliked") && !row.disliked) return false;
    if (filters.includes("hideDisliked") && row.disliked) return false;
    if (filters.includes("downloads") && !row.ready) return false;
    if (filters.includes("full") && row.duration > 0 && row.duration < 60) return false;
    return true;
  });

  const sortedRows = [...filteredRows].sort((a, b) => {
    if (sort === "old") return a.createdAt - b.createdAt;
    if (sort === "most") {
      const diff = Number(b.liked) - Number(a.liked);
      return diff || b.createdAt - a.createdAt;
    }
    if (sort === "least") {
      const diff = Number(a.liked) - Number(b.liked);
      return diff || b.createdAt - a.createdAt;
    }
    return b.createdAt - a.createdAt;
  });

  const rowSource =
    tab === "history"
      ? [...filteredRows].sort((a, b) => b.createdAt - a.createdAt)
      : sortedRows;

  const filteredLiked = likedTracks.filter((track) => {
    if (!searchTerm) return true;
    return `${track.title} ${track.artist_name || ""}`.toLowerCase().includes(searchTerm);
  });

  const filteredPlaylists = playlists.filter(
    (playlist) => !searchTerm || playlist.name.toLowerCase().includes(searchTerm)
  );
  const filteredWorkspaces = workspaces.filter(
    (workspace) => !searchTerm || workspace.name.toLowerCase().includes(searchTerm)
  );
  const filteredProjects = projects.filter(
    (project) => !searchTerm || project.title.toLowerCase().includes(searchTerm)
  );

  const isRowTab = tab === "songs" || tab === "history" || tab === "covers";
  const activeCount = tab === "likedHooks" ? filteredLiked.length : isRowTab ? rowSource.length : 0;
  const pageCount = Math.max(1, Math.ceil(activeCount / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageSlice = [(currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE] as const;
  const pageRows = isRowTab ? rowSource.slice(pageSlice[0], pageSlice[1]) : [];
  const likedPageRows =
    tab === "likedHooks" ? filteredLiked.slice(pageSlice[0], pageSlice[1]) : [];

  const coverRows = pageRows.filter(
    (row, index, all) =>
      Boolean(row.clip.image_url) &&
      all.findIndex((item) => item.clip.image_url === row.clip.image_url) === index
  );

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  const activeFilterCount = filters.length;
  const selectedClip =
    detail && detail.clips?.length
      ? detail.clips.find((clip) => clip.variant === detailVariant) ?? detail.clips[0]
      : detail
        ? generationClips(detail)[0]
        : null;
  const detailReady = detail && selectedClip ? clipIsReady(detail, selectedClip) : false;
  const detailCover = selectedClip?.image_url || "/hero.png";
  const detailInstrumental = detail ? generationIsInstrumental(detail) : false;
  const sortLabel = SORT_OPTIONS.find((option) => option.id === sort)?.label ?? "Newest";
  const showPager =
    !bootLoading &&
    (tab === "songs" || tab === "history" || tab === "covers" || tab === "likedHooks") &&
    activeCount > 0;

  function playClip(song: WebMusicGeneration, clip: WebMusicClip) {
    if (!clipIsReady(song, clip)) return;
    const variant = clip.variant || "ok";
    const audioUrl =
      clip.audio_url ||
      clip.download_url ||
      `/api/v3/web-music/generations/${song.id}/stream/${variant}`;
    if (!audioUrl) return;
    playTrack({
      title: clip.title || song.title || "Untitled",
      artist: "You",
      cover: clip.image_url || "/hero.png",
      duration: Math.max(1, Math.round(clip.duration_seconds || 180)),
      audioUrl,
    });
  }

  function playLiked(track: LikedTrack) {
    playTrack({
      title: track.title,
      artist: track.artist_name || "Camxora",
      cover: track.cover_url || "/hero.png",
      duration: Math.max(1, Math.round(track.duration_seconds || 180)),
      audioUrl: `/api/v3/streaming/tracks/${encodeURIComponent(track.id)}/stream`,
    });
  }

  function playPlaylistItem(item: WebMusicPlaylistItem) {
    if (!item.audio_url) return;
    playTrack({
      title: item.title || "Untitled",
      artist: "You",
      cover: item.image_url || "/hero.png",
      duration: 180,
      audioUrl: item.audio_url,
    });
  }

  async function toggleLike(song: WebMusicGeneration, clip: WebMusicClip) {
    const key = clipTrackKey(song.id, clip.variant);
    const nextLiked = !likedKeys.includes(key);
    setLikedKeys((current) =>
      nextLiked ? [...current, key] : current.filter((item) => item !== key)
    );
    setToast(nextLiked ? "Saved to Liked" : "Removed from Liked");
    try {
      await likeWebMusicGeneration(song.id, clip.variant, nextLiked);
    } catch {
      setLikedKeys((current) =>
        nextLiked ? current.filter((item) => item !== key) : [...current, key]
      );
      setToast("Could not update like");
    }
  }

  function toggleDislike(song: WebMusicGeneration, clip: WebMusicClip) {
    const key = clipTrackKey(song.id, clip.variant);
    setDislikedKeys((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key]
    );
  }

  async function copyClipLink(song: WebMusicGeneration, clip: WebMusicClip) {
    const url = `${window.location.origin}/library?clip=${encodeURIComponent(
      song.id
    )}&variant=${encodeURIComponent(clip.variant)}`;
    try {
      await navigator.clipboard.writeText(url);
      setToast("Link copied");
    } catch {
      setToast(url);
    }
  }

  function openDetail(song: WebMusicGeneration, clip: WebMusicClip) {
    setDetail(song);
    setDetailId(song.id);
    setDetailVariant(clip.variant);
    setDetailOpen(true);
    const url = new URL(window.location.href);
    url.searchParams.set("clip", song.id);
    url.searchParams.set("variant", clip.variant);
    window.history.replaceState({}, "", url.toString());
    void openDetailById(song.id, clip.variant);
  }

  function closeDetail() {
    setDetailOpen(false);
    const url = new URL(window.location.href);
    url.searchParams.delete("clip");
    url.searchParams.delete("variant");
    window.history.replaceState({}, "", url.toString());
  }

  async function openDetailById(id: string, variant?: string) {
    setDetailId(id);
    setDetailOpen(true);
    setDetailLoading(true);
    if (variant) setDetailVariant(variant);
    try {
      const next = await getWebMusicGeneration(id);
      if (!mounted.current) return;
      setDetail(next);
      setDetailVariant(
        (current) => variant ?? current ?? next.clips?.[0]?.variant ?? "ok"
      );
      setGenerations((current) => current.map((item) => (item.id === next.id ? next : item)));
    } catch (cause) {
      if (mounted.current) {
        setToast(cause instanceof Error ? cause.message : "Could not load this track");
      }
    } finally {
      if (mounted.current) setDetailLoading(false);
    }
  }

  async function unlockPreview() {
    if (!detail) return;
    setDetailLoading(true);
    try {
      const updated = await unlockWebMusicPreview(detail.id);
      if (!mounted.current) return;
      setDetail(updated);
      setGenerations((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      setToast("Full song unlocked");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not unlock this track");
    } finally {
      if (mounted.current) setDetailLoading(false);
    }
  }

  async function deleteGenerations(ids: string[]) {
    setConfirm(null);
    if (!ids.length || deleting) return;
    setDeleting(true);
    const deleted: string[] = [];
    const failures: string[] = [];
    for (const id of ids) {
      try {
        await deleteWebMusicGeneration(id);
        deleted.push(id);
      } catch (cause) {
        failures.push(cause instanceof Error ? cause.message : "Could not delete song");
      }
    }
    if (!mounted.current) return;
    const gone = new Set(deleted);
    setGenerations((current) => current.filter((item) => !gone.has(item.id)));
    setTotalGenerations((current) => Math.max(0, current - deleted.length));
    setSelectedIds((current) => current.filter((id) => !gone.has(id)));
    if (detailId && gone.has(detailId)) {
      closeDetail();
      setDetail(null);
      setDetailId(null);
      setDetailVariant(null);
    }
    setDeleting(false);
    setToast(
      deleted.length === 1 ? "Song deleted" : `${deleted.length} songs deleted`
    );
    if (failures.length) setError(failures[0]);
    if (!deleted.length) setToast("Could not delete song");
  }

  async function deletePlaylist(playlist: WebMusicPlaylistSummary) {
    setConfirm(null);
    if (deleting) return;
    setDeleting(true);
    try {
      await deleteWebMusicPlaylist(playlist.id);
      if (!mounted.current) return;
      setPlaylists((current) => current.filter((item) => item.id !== playlist.id));
      if (playlistDetail?.id === playlist.id) setPlaylistDetail(null);
      setToast("Playlist deleted");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not delete playlist");
    } finally {
      if (mounted.current) setDeleting(false);
    }
  }

  async function openPlaylist(playlist: WebMusicPlaylistSummary) {
    setPlaylistDetail(playlist);
    setPlaylistItems([]);
    setPlaylistError("");
    setPlaylistItemsLoading(true);
    try {
      const payload = await listWebMusicPlaylistItems(playlist.id);
      if (mounted.current) setPlaylistItems(payload.items);
    } catch (cause) {
      if (mounted.current) {
        setPlaylistError(cause instanceof Error ? cause.message : "Could not load this playlist");
      }
    } finally {
      if (mounted.current) setPlaylistItemsLoading(false);
    }
  }

  async function submitComposer() {
    const name = composerName.trim();
    if (!composer || !name || composerBusy) return;
    setComposerBusy(true);
    try {
      if (composer === "playlist") {
        const created = await createWebMusicPlaylist(name);
        if (!mounted.current) return;
        setPlaylists((current) => [created, ...current]);
        setToast(`Created playlist "${created.name}"`);
      } else {
        const created = await createWebMusicWorkspace(name);
        if (!mounted.current) return;
        setWorkspaces((current) => [...current, created]);
        setToast(`Created workspace "${created.name}"`);
      }
      setComposer(null);
      setComposerName("");
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : "Could not create");
    } finally {
      if (mounted.current) setComposerBusy(false);
    }
  }

  function toggleTrash() {
    if (trashMode) {
      setTrashMode(false);
      setSelectedIds([]);
      return;
    }
    setTrashMode(true);
    setSelectedIds([]);
    setTab("songs");
  }

  function toggleSelected(id: string) {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    );
  }

  function selectAllVisible() {
    setSelectedIds(Array.from(new Set(pageRows.map((row) => row.song.id))));
  }

  function clearFilters() {
    setSearch("");
    setFilters([]);
  }

  const skeletonRows = (
    <>
      {[0, 1, 2, 3, 4].map((item) => (
        <div className="s-skel" key={item}>
          <span className="a" />
          <span className="b">
            <i />
            <i />
          </span>
        </div>
      ))}
    </>
  );

  const renderEmpty = (icon: string, title: string, copy: string, action?: ReactNode) => (
    <div className="s-empty">
      <span className="ico">
        <Icon name={icon} />
      </span>
      <b>{title}</b>
      <p>{copy}</p>
      {action}
    </div>
  );

  const noResults = renderEmpty(
    "fa-magnifying-glass",
    "No results",
    "Try a different search or clear your filters.",
    <button type="button" className="s-btn s-btn-secondary" onClick={clearFilters}>
      Clear filters
    </button>
  );

  const hasSearch = Boolean(searchTerm) || activeFilterCount > 0;

  const renderClipRow = (row: LibRow) => {
    const { song, clip, key, title, ready, duration, liked, disliked } = row;
    const selectedForTrash = trashMode && selectedIds.includes(song.id);
    return (
      <div
        className={`s-row${selectedForTrash ? " selected" : ""}`}
        key={key}
        role="group"
        aria-label={title}
        onClick={() => {
          if (trashMode) toggleSelected(song.id);
          else openDetail(song, clip);
        }}
      >
        {trashMode ? (
          <button
            type="button"
            className={`s-selectbox${selectedForTrash ? " on" : ""}`}
            aria-label={`Select ${title}`}
            aria-pressed={selectedForTrash}
            onClick={(event) => {
              event.stopPropagation();
              toggleSelected(song.id);
            }}
          >
            {selectedForTrash ? <Icon name="fa-check" /> : null}
          </button>
        ) : null}

        <button
          type="button"
          className="s-cover"
          aria-label={ready ? `Play ${title}` : "Song not ready"}
          onClick={(event) => {
            event.stopPropagation();
            if (ready) playClip(song, clip);
          }}
        >
          <img src={clip.image_url || "/hero.png"} alt="" loading="lazy" />
          <span className="s-cover-play">
            <span>
              <Icon name={ready ? "fa-play" : "fa-hourglass-half"} />
            </span>
          </span>
          {duration ? <span className="s-dur">{formatClipDuration(duration)}</span> : null}
        </button>

        <div className="s-row-body">
          <div className="s-row-title">
            <a
              href={`/library?clip=${encodeURIComponent(song.id)}&variant=${encodeURIComponent(
                clip.variant
              )}`}
              onClick={(event) => {
                event.preventDefault();
                openDetail(song, clip);
              }}
            >
              {title}
            </a>
            <span className="s-tag">{song.model_label || song.model || "V6"}</span>
            {!ready ? (
              <span className={`s-status ${statusClass(song.status)}`}>
                {statusLabel(song.status)}
              </span>
            ) : null}
            {song.is_preview ? <span className="s-status live">Preview</span> : null}
          </div>
          <div className="s-row-desc">
            {clipVersionLabel(clip.variant)} · {song.style || "No style tags"}
          </div>
          <div className="s-row-actions" onClick={(event) => event.stopPropagation()}>
            <button
              type="button"
              className="s-act"
              aria-label={ready ? `Play ${title}` : "Song not ready"}
              disabled={!ready}
              onClick={() => playClip(song, clip)}
            >
              <Icon name="fa-play" /> Play
            </button>
            <button
              type="button"
              className={`s-act icon-only${liked ? " on" : ""}`}
              aria-label={liked ? "Unlike clip" : "Like clip"}
              aria-pressed={liked}
              onClick={() => void toggleLike(song, clip)}
            >
              <Icon name="fa-heart" />
            </button>
            <button
              type="button"
              className={`s-act icon-only${disliked ? " on" : ""}`}
              aria-label="Dislike clip"
              aria-pressed={disliked}
              onClick={() => toggleDislike(song, clip)}
            >
              <Icon name="fa-thumbs-down" />
            </button>
            <button
              type="button"
              className="s-act"
              aria-label="Share clip"
              onClick={() => void copyClipLink(song, clip)}
            >
              <Icon name="fa-share" /> Share
            </button>
            <Link className="s-act" href="/studio/editor" aria-label="Remix or edit clip">
              <Icon name="fa-wand-magic-sparkles" /> Remix
            </Link>
          </div>
        </div>

        <div
          className="s-anchor"
          data-s-menu
          style={{ position: "static" }}
          onClick={(event) => event.stopPropagation()}
        >
          <button
            type="button"
            className="s-row-more"
            aria-label="More options"
            aria-expanded={rowMenuKey === key}
            onClick={() => setRowMenuKey((current) => (current === key ? null : key))}
          >
            <Icon name="fa-ellipsis-vertical" />
          </button>
          {rowMenuKey === key ? (
            <div className="s-menu" role="menu" style={{ right: 12, top: 64, minWidth: 220 }}>
              <button
                type="button"
                className="s-menu-item"
                role="menuitem"
                onClick={() => {
                  setRowMenuKey(null);
                  void copyClipLink(song, clip);
                }}
              >
                <Icon name="fa-link" /> Copy link
              </button>
              <button
                type="button"
                className="s-menu-item"
                role="menuitem"
                disabled={!ready}
                onClick={() => {
                  setRowMenuKey(null);
                  openDetail(song, clip);
                }}
              >
                <Icon name="fa-list" /> Add to playlist
              </button>
              <div className="s-menu-sep" />
              {DOWNLOAD_KINDS.filter(
                (format) =>
                  format.kind === "mp3" ||
                  format.kind === "wav" ||
                  !generationIsInstrumental(song)
              ).map((format) => (
                <a
                  key={format.kind}
                  className="s-menu-item"
                  role="menuitem"
                  href={
                    format.kind === "mp3" && clip.download_url
                      ? clip.download_url
                      : clipDownloadUrl(song.id, clip.variant, format.kind)
                  }
                  onClick={() => setRowMenuKey(null)}
                >
                  <Icon name="fa-download" /> {format.label}
                </a>
              ))}
              <div className="s-menu-sep" />
              <button
                type="button"
                className="s-menu-item"
                role="menuitem"
                onClick={() => {
                  setRowMenuKey(null);
                  window.location.href = `/publish?clip=${encodeURIComponent(song.id)}`;
                }}
              >
                <Icon name="fa-arrow-up-from-bracket" /> Publish
              </button>
              <Link
                className="s-menu-item"
                role="menuitem"
                href="/studio/editor"
                onClick={() => setRowMenuKey(null)}
              >
                <Icon name="fa-table-columns" /> Open in Studio
              </Link>
              <button
                type="button"
                className="s-menu-item"
                role="menuitem"
                disabled={deleting}
                onClick={() => {
                  setRowMenuKey(null);
                  setConfirm({ kind: "generations", ids: [song.id] });
                }}
              >
                <Icon name="fa-trash" /> Delete
              </button>
            </div>
          ) : null}
        </div>
      </div>
    );
  };

  const renderGridCard = (row: LibRow) => (
    <div
      className="s-card"
      key={row.key}
      role="button"
      tabIndex={0}
      onClick={() => openDetail(row.song, row.clip)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") openDetail(row.song, row.clip);
      }}
    >
      <div className="s-card-cover">
        <img src={row.clip.image_url || "/hero.png"} alt="" loading="lazy" />
      </div>
      <b>{row.title}</b>
      <small>{row.song.style || "No style tags"}</small>
    </div>
  );

  const renderLikedRow = (track: LikedTrack) => (
    <div
      className="s-row"
      key={track.id}
      role="group"
      aria-label={track.title}
      onClick={() => playLiked(track)}
    >
      <button
        type="button"
        className="s-cover"
        aria-label={`Play ${track.title}`}
        onClick={(event) => {
          event.stopPropagation();
          playLiked(track);
        }}
      >
        <img src={track.cover_url || "/hero.png"} alt="" loading="lazy" />
        <span className="s-cover-play">
          <span>
            <Icon name="fa-play" />
          </span>
        </span>
      </button>
      <div className="s-row-body">
        <div className="s-row-title">
          <b>{track.title}</b>
          <span className="s-tag">Hook</span>
        </div>
        <div className="s-row-desc">
          {track.artist_name || "Camxora"}
          {track.duration_seconds ? ` · ${formatClipDuration(track.duration_seconds)}` : ""}
          {track.added_at ? ` · ${formatDate(track.added_at)}` : ""}
        </div>
        <div className="s-row-actions" onClick={(event) => event.stopPropagation()}>
          <button
            type="button"
            className="s-act"
            aria-label={`Play ${track.title}`}
            onClick={() => playLiked(track)}
          >
            <Icon name="fa-play" /> Play
          </button>
        </div>
      </div>
    </div>
  );

  const renderPlaylistCard = (playlist: WebMusicPlaylistSummary) => (
    <button
      type="button"
      className="s-playlist"
      key={playlist.id}
      onClick={() => void openPlaylist(playlist)}
    >
      <span className="s-playlist-cover">
        <Icon name="fa-music" />
      </span>
      <b>{playlist.name}</b>
      <small>
        {playlist.song_count ?? 0} {playlist.song_count === 1 ? "track" : "tracks"} ·{" "}
        {playlist.is_public ? "Public" : "Private"}
      </small>
    </button>
  );

  const tabBody = () => {
    if (bootLoading) return skeletonRows;

    if (tab === "songs" || tab === "history") {
      if (!rowSource.length) {
        return hasSearch
          ? noResults
          : renderEmpty(
              tab === "history" ? "fa-clock" : "fa-music",
              tab === "history" ? "No history yet" : "No songs yet",
              tab === "history"
                ? "Your generation history will show up here."
                : "Describe a song or write lyrics, then hit Create.",
              <Link className="s-btn s-btn-primary" href="/create">
                <Icon name="fa-plus" /> Create a song
              </Link>
            );
      }
      return <>{pageRows.map(renderClipRow)}</>;
    }

    if (tab === "covers") {
      if (!coverRows.length) {
        return hasSearch
          ? noResults
          : renderEmpty(
              "fa-image",
              "No cover art yet",
              "Covers from your generated songs will collect here."
            );
      }
      return <div className="s-grid">{coverRows.map(renderGridCard)}</div>;
    }

    if (tab === "playlists") {
      return (
        <>
          <div className="s-playlists">
            <button
              type="button"
              className="s-playlist"
              onClick={() => {
                setComposerName("");
                setComposer("playlist");
              }}
            >
              <span className="s-playlist-cover">
                <Icon name="fa-plus" />
              </span>
              <b>New playlist</b>
              <small>Group your favourite tracks</small>
            </button>
            {filteredPlaylists.map(renderPlaylistCard)}
          </div>
          {!filteredPlaylists.length ? (
            <p className="s-note" style={{ padding: "8px 0" }}>
              {hasSearch ? "No playlists match your search." : "No playlists yet."}
            </p>
          ) : null}
        </>
      );
    }

    if (tab === "workspaces") {
      return (
        <>
          <div className="s-playlists">
            <button
              type="button"
              className="s-playlist"
              onClick={() => {
                setComposerName("");
                setComposer("workspace");
              }}
            >
              <span className="s-playlist-cover">
                <Icon name="fa-plus" />
              </span>
              <b>New workspace</b>
              <small>Keep projects and songs together</small>
            </button>
            {filteredWorkspaces.map((workspace) => (
              <div className="s-playlist" key={workspace.id}>
                <span className="s-playlist-cover">
                  <Icon name="fa-folder" />
                </span>
                <b>{workspace.name}</b>
                <small>
                  {workspace.is_default ? "Default workspace" : "Workspace"}
                  {workspace.created_at ? ` · ${formatDate(workspace.created_at)}` : ""}
                </small>
              </div>
            ))}
          </div>
          <p className="s-note" style={{ padding: "8px 0" }}>
            Choose a workspace from the Create page to save new songs into it.
          </p>
        </>
      );
    }

    if (tab === "projects") {
      if (!filteredProjects.length) {
        return hasSearch
          ? noResults
          : renderEmpty(
              "fa-table-columns",
              "No studio projects yet",
              "Save a project in the Studio editor and it will appear here.",
              <Link className="s-btn s-btn-secondary" href="/studio/editor">
                <Icon name="fa-table-columns" /> Open Studio
              </Link>
            );
      }
      return (
        <div className="s-playlists">
          {filteredProjects.map((project) => (
            <Link className="s-playlist" key={project.id} href="/studio/editor">
              <span className="s-playlist-cover">
                <Icon name="fa-table-columns" />
              </span>
              <b>{project.title}</b>
              <small>
                v{project.major_version} · {project.bpm} BPM · {project.time_signature}
                {project.updated_at ? ` · ${formatDate(project.updated_at)}` : ""}
              </small>
            </Link>
          ))}
        </div>
      );
    }

    if (tab === "likedHooks") {
      if (!filteredLiked.length) {
        return hasSearch
          ? noResults
          : renderEmpty(
              "fa-heart",
              "No liked hooks yet",
              "Tracks you like while listening will appear here."
            );
      }
      return <>{likedPageRows.map(renderLikedRow)}</>;
    }

    if (tab === "albums") {
      return renderEmpty(
        "fa-compact-disc",
        "No albums yet",
        "Albums published from the artist dashboard will appear here.",
        <Link className="s-btn s-btn-secondary" href="/artist-dashboard">
          Open artist dashboard
        </Link>
      );
    }

    return renderEmpty(
      "fa-wand-magic-sparkles",
      "Hooks are not enabled yet",
      "Short hook generation is not available in this workspace. Create a full song instead.",
      <Link className="s-btn s-btn-secondary" href="/create">
        Create a song
      </Link>
    );
  };

  if (authLoading) {
    return (
      <div className="s-page">
        <div className="s-lib">
          <div className="s-lib-head">
            <h1 className="s-lib-title">Library</h1>
          </div>
          <div className="s-lib-body">
            <div className="s-lib-tools" />
            {skeletonRows}
          </div>
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="s-page">
      <div className="s-lib-shell">
        <div className="s-lib">
        <div className="s-lib-head">
          <h1 className="s-lib-title">Library</h1>
          <div className="s-lib-actions">
            <div className="s-anchor" data-s-menu>
              <button
                type="button"
                className="s-pill"
                aria-expanded={audioMenuOpen}
                aria-label="Audio actions"
                onClick={() => setAudioMenuOpen((value) => !value)}
              >
                Audio <Icon name="fa-plus" />
              </button>
              {audioMenuOpen ? (
                <div className="s-menu" role="menu" style={{ top: 50, right: 0, width: 190 }}>
                  <button
                    type="button"
                    className="s-menu-item"
                    role="menuitem"
                    onClick={() => {
                      setAudioMenuOpen(false);
                      setAttachNotice("upload");
                    }}
                  >
                    <Icon name="fa-arrow-up-from-bracket" /> Upload
                  </button>
                  <button
                    type="button"
                    className="s-menu-item"
                    role="menuitem"
                    onClick={() => {
                      setAudioMenuOpen(false);
                      setAttachNotice("record");
                    }}
                  >
                    <Icon name="fa-microphone" /> Record
                  </button>
                </div>
              ) : null}
            </div>
            <button
              type="button"
              className={`s-btn s-btn-icon${trashMode ? " s-btn-secondary" : ""}`}
              aria-label={trashMode ? "Exit trash" : "Open trash"}
              aria-pressed={trashMode}
              title="Trash"
              onClick={toggleTrash}
            >
              <Icon name="fa-trash" />
            </button>
          </div>
        </div>

        <div
          className={`s-tabs-sm${tabsOverflow ? " has-overflow" : ""}`}
          role="tablist"
          aria-label="Library sections"
          ref={tabListRef}
        >
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              className={`s-tab${tab === item.id ? " on" : ""}`}
              aria-selected={tab === item.id}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </button>
          ))}
          <span
            className="s-tab-indicator"
            aria-hidden="true"
            style={{ left: indicator.left, width: indicator.width }}
          />
        </div>

        {trashMode ? (
          <div className="s-lib-bar">
            <span className="s-note">{selectedIds.length} selected</span>
            <span className="s-spacer" />
            <button
              type="button"
              className="s-btn s-btn-sm s-btn-secondary"
              onClick={selectAllVisible}
              disabled={!pageRows.length}
            >
              Select all
            </button>
            <button
              type="button"
              className="s-btn s-btn-sm s-danger-text"
              onClick={() => setConfirm({ kind: "generations", ids: selectedIds })}
              disabled={!selectedIds.length || deleting}
            >
              <Icon name="fa-trash" /> Delete selected
            </button>
            <button
              type="button"
              className="s-btn s-btn-sm s-btn-ghost"
              onClick={() => {
                setTrashMode(false);
                setSelectedIds([]);
              }}
            >
              Cancel
            </button>
          </div>
        ) : null}

        <div className="s-lib-tools">
          <label className="s-search">
            <Icon name="fa-magnifying-glass" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search"
              aria-label="Search library"
            />
          </label>

          <div className="s-anchor" data-s-menu>
            <button
              type="button"
              className={`s-pill${activeFilterCount ? " on" : ""}`}
              onClick={() => setFiltersOpen((value) => !value)}
              aria-expanded={filtersOpen}
              aria-label={`Filters (${activeFilterCount})`}
            >
              <Icon name="fa-filter" /> <span className="s-btn-label">Filters{activeFilterCount ? ` (${activeFilterCount})` : ""}</span>
            </button>
            {filtersOpen ? (
              <div className="s-menu" role="menu" style={{ top: 46, right: 0, width: 200 }}>
                {filterOptions.map((option) => {
                  const on = filters.includes(option.id);
                  return (
                    <button
                      key={option.id}
                      type="button"
                      className={`s-menu-item${on ? " on" : ""}`}
                      role="menuitemcheckbox"
                      aria-checked={on}
                      disabled={option.disabled}
                      onClick={() =>
                        setFilters((current) =>
                          current.includes(option.id)
                            ? current.filter((item) => item !== option.id)
                            : [...current, option.id]
                        )
                      }
                    >
                      {option.label}
                      {option.disabled ? (
                        <span className="check">—</span>
                      ) : on ? (
                        <span className="check">✓</span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>

          <div className="s-anchor" data-s-menu>
            <button
              type="button"
              className="s-pill"
              onClick={() => setSortOpen((value) => !value)}
              aria-expanded={sortOpen}
              aria-label={`Sort: ${sortLabel}`}
            >
              {sortLabel}
              <Icon name="fa-chevron-down" />
            </button>
            {sortOpen ? (
              <div className="s-menu" role="menu" style={{ top: 46, right: 0, width: 180 }}>
                {SORT_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className="s-menu-item"
                    role="menuitemradio"
                    aria-checked={sort === option.id}
                    onClick={() => {
                      setSort(option.id);
                      setSortOpen(false);
                    }}
                  >
                    {option.label}
                    {sort === option.id ? <span className="check">✓</span> : null}
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <button
            type="button"
            className={`s-pill${filters.includes("liked") ? " on" : ""}`}
            aria-pressed={filters.includes("liked")}
            onClick={() =>
              setFilters((current) =>
                current.includes("liked")
                  ? current.filter((item) => item !== "liked")
                  : [...current, "liked"]
              )
            }
          >
            Liked
          </button>
          <button
            type="button"
            className="s-pill"
            disabled
            title="Public visibility is not available yet"
          >
            Public
          </button>
          <button
            type="button"
            className="s-pill"
            disabled
            title="Uploads are not available yet"
          >
            Uploads
          </button>
        </div>

        {error ? (
          <p className="s-error" role="alert">
            {error}
          </p>
        ) : null}

        <div className="s-lib-body">{tabBody()}</div>

        {showPager ? (
          <div className="s-lib-foot">
            <span className="s-note">Page</span>
            <div className="s-pager">
              <input
                aria-label="Page number"
                value={currentPage}
                onChange={(event) => {
                  const next = Number(event.target.value.replace(/\D/g, "")) || 1;
                  setPage(Math.min(pageCount, Math.max(1, next)));
                }}
              />
              <button
                type="button"
                aria-label="Previous page"
                onClick={() => setPage((value) => Math.max(1, value - 1))}
                disabled={currentPage <= 1}
              >
                <Icon name="fa-chevron-left" />
              </button>
              <button
                type="button"
                aria-label="Next page"
                onClick={() => {
                  if (currentPage < pageCount) setPage(currentPage + 1);
                  else if (tab !== "likedHooks" && generations.length < totalGenerations) {
                    void loadGenerations(generations.length);
                  }
                }}
                disabled={
                  currentPage >= pageCount &&
                  (tab === "likedHooks" || generations.length >= totalGenerations)
                }
              >
                <Icon name="fa-chevron-right" />
              </button>
            </div>
            {tab !== "likedHooks" && generations.length < totalGenerations ? (
              <button
                type="button"
                className="s-chip"
                onClick={() => void loadGenerations(generations.length)}
                disabled={loadingMore}
              >
                {loadingMore ? "Loading..." : `Load more (${generations.length}/${totalGenerations})`}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

        {detailOpen ? (
          <TrackRail
            key={detail?.id ?? "empty"}
            detail={detail}
            clip={selectedClip}
            liked={detail && selectedClip ? isLikedRow(detail, selectedClip) : false}
            playlists={playlists}
            loading={detailLoading}
            onClose={closeDetail}
            onPlay={() => {
              if (detail && selectedClip) playClip(detail, selectedClip);
            }}
            onLike={() => {
              if (detail && selectedClip) void toggleLike(detail, selectedClip);
            }}
            onUnlock={() => void unlockPreview()}
            onDelete={() => {
              if (detail) setConfirm({ kind: "generations", ids: [detail.id] });
            }}
            onRename={async (nextTitle, variant) => {
              if (!detail) return false;
              try {
                const updated = await updateWebMusicGenerationTitle(detail.id, nextTitle, variant);
                if (!mounted.current) return false;
                setDetail(updated);
                setGenerations((current) =>
                  current.map((item) => (item.id === updated.id ? updated : item))
                );
                setToast("Title updated");
                return true;
              } catch (cause) {
                setToast(cause instanceof Error ? cause.message : "Could not rename this track");
                return false;
              }
            }}
            onAddToPlaylist={async (playlist) => {
              if (!detail || !selectedClip?.ready) return;
              try {
                await addWebMusicPlaylistItem(playlist.id, detail.id, selectedClip.variant);
                setToast(`Added to ${playlist.name}`);
              } catch (cause) {
                setToast(cause instanceof Error ? cause.message : "Could not add to playlist");
              }
            }}
            onCreatePlaylist={async (name) => {
              try {
                const created = await createWebMusicPlaylist(name);
                if (mounted.current) setPlaylists((current) => [created, ...current]);
                setToast(`Created playlist "${created.name}"`);
                return created;
              } catch (cause) {
                setToast(cause instanceof Error ? cause.message : "Could not create playlist");
                return null;
              }
            }}
          />
        ) : null}
      </div>

      {playlistDetail ? (
        <div
          className="s-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={playlistDetail.name}
          onClick={() => setPlaylistDetail(null)}
        >
          <div
            className="s-modal"
            style={{ width: "min(620px,100%)" }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="s-modal-head">
              <h3>{playlistDetail.name}</h3>
              <button
                type="button"
                className="s-btn s-btn-icon sm"
                aria-label="Close"
                onClick={() => setPlaylistDetail(null)}
              >
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="s-modal-body">
              {playlistItemsLoading ? (
                <p className="s-note">Loading tracks...</p>
              ) : playlistError ? (
                <p className="s-error">{playlistError}</p>
              ) : playlistItems.length ? (
                <div>
                  {playlistItems.map((item) => (
                    <div
                      className="s-row"
                      key={item.id}
                      role="button"
                      tabIndex={0}
                      style={{ padding: 8 }}
                      onClick={() => playPlaylistItem(item)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") playPlaylistItem(item);
                      }}
                    >
                      <span className="s-cover s-cover-sm">
                        <img src={item.image_url || "/hero.png"} alt="" loading="lazy" />
                        <span className="s-cover-play">
                          <span>
                            <Icon name="fa-play" />
                          </span>
                        </span>
                      </span>
                      <div className="s-row-body" style={{ paddingRight: 0 }}>
                        <div className="s-row-title">
                          <b>{item.title || "Untitled"}</b>
                          <span className="s-tag">{clipVersionLabel(item.variant)}</span>
                        </div>
                        <div className="s-row-desc">{item.style || "No style tags"}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="s-note">This playlist is empty.</p>
              )}
            </div>
            <div className="s-modal-foot">
              <button
                type="button"
                className="s-btn s-btn-ghost s-danger-text"
                onClick={() => setConfirm({ kind: "playlist", playlist: playlistDetail })}
                disabled={deleting}
              >
                <Icon name="fa-trash" /> Delete playlist
              </button>
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className="s-btn s-btn-secondary"
                onClick={() => setPlaylistDetail(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {composer ? (
        <div
          className="s-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={composer === "playlist" ? "New playlist" : "New workspace"}
          onClick={() => setComposer(null)}
        >
          <div
            className="s-modal"
            style={{ width: "min(440px,100%)" }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="s-modal-head">
              <h3>{composer === "playlist" ? "New playlist" : "New workspace"}</h3>
              <button
                type="button"
                className="s-btn s-btn-icon sm"
                aria-label="Close"
                onClick={() => setComposer(null)}
              >
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="s-modal-body">
              <label className="s-field">
                <span className="s-field-label">
                  {composer === "playlist" ? "Playlist name" : "Workspace name"}
                </span>
                <input
                  className="s-input"
                  autoFocus
                  value={composerName}
                  onChange={(event) => setComposerName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void submitComposer();
                  }}
                  maxLength={120}
                  placeholder={composer === "playlist" ? "My playlist" : "My workspace"}
                />
              </label>
            </div>
            <div className="s-modal-foot">
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className="s-btn s-btn-ghost"
                onClick={() => setComposer(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="s-btn s-btn-primary"
                onClick={() => void submitComposer()}
                disabled={composerBusy || !composerName.trim()}
              >
                {composerBusy ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {attachNotice ? (
        <div
          className="s-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={attachNotice === "upload" ? "Upload audio" : "Record audio"}
          onClick={() => setAttachNotice(null)}
        >
          <div
            className="s-modal"
            style={{ width: "min(500px,100%)" }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="s-modal-head">
              <h3>{attachNotice === "upload" ? "Upload audio" : "Record audio"}</h3>
              <button
                type="button"
                className="s-btn s-btn-icon sm"
                aria-label="Close"
                onClick={() => setAttachNotice(null)}
              >
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="s-modal-body">
              <p className="s-note">
                {attachNotice === "upload"
                  ? "Upload your own audio to extend, cover, or remix an idea."
                  : "Record a take and use it as a reference for a new song."}
              </p>
              <div className="s-box">
                Uploads and recording are not enabled for this workspace yet. You can still
                add audio from the Studio editor.
              </div>
            </div>
            <div className="s-modal-foot">
              <Link className="s-btn s-btn-secondary" href="/studio/editor">
                <Icon name="fa-table-columns" /> Open Studio
              </Link>
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className="s-btn s-btn-ghost"
                onClick={() => setAttachNotice(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {confirm ? (
        <div
          className="s-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Confirm delete"
          onClick={() => setConfirm(null)}
        >
          <div
            className="s-modal"
            style={{ width: "min(440px,100%)" }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="s-modal-head">
              <h3>
                {confirm.kind === "generations"
                  ? `Delete ${confirm.ids.length} ${confirm.ids.length === 1 ? "song" : "songs"}?`
                  : "Delete playlist?"}
              </h3>
              <button
                type="button"
                className="s-btn s-btn-icon sm"
                aria-label="Close"
                onClick={() => setConfirm(null)}
              >
                <Icon name="fa-xmark" />
              </button>
            </div>
            <div className="s-modal-body">
              <p className="s-note">
                {confirm.kind === "generations"
                  ? "This permanently removes the selected songs and their files from your library."
                  : `"${confirm.playlist.name}" will be permanently deleted. The songs stay in your library.`}
              </p>
            </div>
            <div className="s-modal-foot">
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className="s-btn s-btn-ghost"
                onClick={() => setConfirm(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="s-btn s-btn-danger"
                disabled={deleting}
                onClick={() => {
                  if (confirm.kind === "generations") void deleteGenerations(confirm.ids);
                  else void deletePlaylist(confirm.playlist);
                }}
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {toast ? (
        <div className="s-toast" role="status">
          {toast}
        </div>
      ) : null}
    </div>
  );
}
