"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { Icon } from "@/components/Icon";
import { useAuth } from "@/components/AuthProvider";
import {
  createStudioProject,
  deleteStudioProject,
  forkStudioProject,
  listStudioProjects,
  updateStudioProject,
  type StudioProject,
} from "@/lib/studio-api";

const PAGE_SIZE = 50;

type SortMode = "updated" | "title";

function relativeTime(value?: string | null): string {
  if (!value) return "never";
  const then = new Date(value).getTime();
  if (!Number.isFinite(then)) return "unknown";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(then).toLocaleDateString();
}

function projectMeta(project: StudioProject): string {
  const parts = [`${project.bpm} BPM`, project.time_signature || "4/4"];
  if (project.comment_count) parts.push(`${project.comment_count} comment${project.comment_count === 1 ? "" : "s"}`);
  return parts.join(" · ");
}

export function StudioHome({ marketing }: { marketing: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [projects, setProjects] = useState<StudioProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortMode>("updated");
  const [showArchived, setShowArchived] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [actionError, setActionError] = useState("");
  const [menuId, setMenuId] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<StudioProject | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<StudioProject | null>(null);
  const renameInputRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(
    async (includeArchived: boolean) => {
      setLoading(true);
      setError("");
      try {
        const result = await listStudioProjects(PAGE_SIZE, 0, includeArchived);
        setProjects(result.items || []);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Could not load your projects.");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (authLoading || !user) return;
    void load(showArchived);
  }, [authLoading, user, showArchived, load]);

  useEffect(() => {
    if (!menuId) return;
    function onPointerDown(event: MouseEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.closest("[data-studio-project-menu]")) return;
      setMenuId(null);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuId(null);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuId]);

  useEffect(() => {
    if (!renameTarget) return;
    const handle = window.setTimeout(() => {
      renameInputRef.current?.focus();
      renameInputRef.current?.select();
    }, 20);
    return () => window.clearTimeout(handle);
  }, [renameTarget]);

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const filtered = needle
      ? projects.filter((project) => {
          if (project.title.toLowerCase().includes(needle)) return true;
          return (project.tags || []).some((tag) => tag.toLowerCase().includes(needle));
        })
      : projects.slice();
    filtered.sort((a, b) => {
      if (Boolean(a.pinned) !== Boolean(b.pinned)) return a.pinned ? -1 : 1;
      if (sort === "title") return a.title.localeCompare(b.title);
      return new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime();
    });
    return filtered;
  }, [projects, search, sort]);

  const resume = useMemo(() => {
    const active = projects.filter((project) => !project.archived);
    if (!active.length) return null;
    return active.slice().sort((a, b) => {
      if (Boolean(a.pinned) !== Boolean(b.pinned)) return a.pinned ? -1 : 1;
      return new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime();
    })[0];
  }, [projects]);

  function openProject(project: StudioProject) {
    setMenuId(null);
    router.push(`/studio/editor?project=${encodeURIComponent(project.id)}`);
  }

  async function createProject() {
    if (creating) return;
    setCreating(true);
    setActionError("");
    try {
      const created = await createStudioProject({
        title: "Untitled project",
        bpm: 120,
        time_signature: "4/4",
        data: {},
      });
      router.push(`/studio/editor?project=${encodeURIComponent(created.id)}`);
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Could not create a project.");
      setCreating(false);
    }
  }

  async function runAction(project: StudioProject, action: () => Promise<void>) {
    setBusyId(project.id);
    setActionError("");
    try {
      await action();
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "That action failed.");
    } finally {
      setBusyId(null);
    }
  }

  async function duplicate(project: StudioProject) {
    await runAction(project, async () => {
      const copy = await forkStudioProject(project.id, `${project.title} (copy)`);
      setProjects((current) => [copy, ...current]);
      setMenuId(null);
    });
  }

  async function togglePin(project: StudioProject) {
    await runAction(project, async () => {
      const next = !project.pinned;
      const saved = await updateStudioProject(project.id, { pinned: next });
      setProjects((current) =>
        current.map((item) => (item.id === project.id ? { ...item, ...saved } : item))
      );
      setMenuId(null);
    });
  }

  async function toggleArchive(project: StudioProject) {
    await runAction(project, async () => {
      const next = !project.archived;
      const saved = await updateStudioProject(project.id, { archived: next });
      setProjects((current) =>
        next
          ? current.filter((item) => item.id !== project.id)
          : current.map((item) => (item.id === project.id ? { ...item, ...saved } : item))
      );
      setMenuId(null);
    });
  }

  async function commitRename() {
    const project = renameTarget;
    if (!project) return;
    const title = renameValue.trim();
    if (!title) return;
    setRenameTarget(null);
    await runAction(project, async () => {
      const saved = await updateStudioProject(project.id, { title });
      setProjects((current) =>
        current.map((item) => (item.id === project.id ? { ...item, ...saved } : item))
      );
    });
  }

  async function commitDelete() {
    const project = deleteTarget;
    if (!project) return;
    setDeleteTarget(null);
    setBusyId(project.id);
    setActionError("");
    try {
      await deleteStudioProject(project.id);
      setProjects((current) => current.filter((item) => item.id !== project.id));
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Could not delete the project.");
    } finally {
      setBusyId(null);
    }
  }

  if (authLoading) {
    return (
      <div className="studio-home" aria-busy="true">
        <div className="studio-home-inner">
          <div className="studio-home-hero sh-skeleton" />
          <div className="studio-home-grid">
            {Array.from({ length: 3 }).map((_, index) => (
              <div className="studio-card sh-skeleton" key={index} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!user) return <>{marketing}</>;

  return (
    <div className="studio-home">
      <div className="studio-home-inner">
        <header className="studio-home-head">
          <div>
            <p className="studio-home-eyebrow">Camxora Studio</p>
            <h1>Your projects</h1>
            <p className="studio-home-sub">
              Pick up where you left off, or start a new arrangement.
            </p>
          </div>
          <div className="studio-home-actions">
            <Link className="btn btn-ghost" href="/create">
              <Icon name="fa-wand-magic-sparkles" /> Create a song
            </Link>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void createProject()}
              disabled={creating}
            >
              <Icon name="fa-plus" /> {creating ? "Creating…" : "New project"}
            </button>
          </div>
        </header>

        {actionError ? (
          <div className="studio-home-alert" role="alert">
            <span>{actionError}</span>
            <button type="button" onClick={() => setActionError("")}>Dismiss</button>
          </div>
        ) : null}

        {loading ? (
          <div className="studio-home-grid">
            {Array.from({ length: 4 }).map((_, index) => (
              <div className="studio-card sh-skeleton" key={index} />
            ))}
          </div>
        ) : error ? (
          <div className="studio-home-state" role="alert">
            <Icon name="fa-triangle-exclamation" />
            <h2>We couldn’t load your projects</h2>
            <p>{error}</p>
            <button type="button" className="btn btn-primary" onClick={() => void load(showArchived)}>
              Try again
            </button>
          </div>
        ) : projects.length === 0 ? (
          <div className="studio-home-state">
            <Icon name="fa-table-columns" />
            <h2>No projects yet</h2>
            <p>
              A project holds your tracks, clips, mixes and versions. Start with an
              empty arrangement, or create a song first and bring it in.
            </p>
            <div className="studio-home-state-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void createProject()}
                disabled={creating}
              >
                {creating ? "Creating…" : "New project"}
              </button>
              <Link className="btn btn-ghost" href="/create">Create a song first</Link>
            </div>
          </div>
        ) : (
          <>
            {resume ? (
              <section className="studio-resume" aria-labelledby="studio-resume-title">
                <div className="studio-resume-body">
                  <p className="studio-home-eyebrow">Resume</p>
                  <h2 id="studio-resume-title">{resume.title}</h2>
                  <p className="studio-home-sub">
                    {projectMeta(resume)} · edited {relativeTime(resume.updated_at)}
                  </p>
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => openProject(resume)}
                >
                  <Icon name="fa-play" /> Open project
                </button>
              </section>
            ) : null}

            <div className="studio-home-toolbar">
              <label className="studio-home-search">
                <Icon name="fa-magnifying-glass" />
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search projects"
                  aria-label="Search projects"
                />
              </label>
              <div className="studio-home-tools">
                <label className="studio-home-toggle">
                  <input
                    type="checkbox"
                    checked={showArchived}
                    onChange={(event) => setShowArchived(event.target.checked)}
                  />
                  Archived
                </label>
                <label className="studio-home-sort">
                  <span>Sort</span>
                  <select
                    value={sort}
                    onChange={(event) => setSort(event.target.value as SortMode)}
                    aria-label="Sort projects"
                  >
                    <option value="updated">Last edited</option>
                    <option value="title">Title</option>
                  </select>
                </label>
              </div>
            </div>

            {visible.length === 0 ? (
              <div className="studio-home-state">
                <Icon name="fa-magnifying-glass" />
                <h2>No projects match “{search}”</h2>
                <p>Try a different title or a tag.</p>
                <button type="button" className="btn btn-ghost" onClick={() => setSearch("")}>
                  Clear search
                </button>
              </div>
            ) : (
              <ul className="studio-home-grid">
                {visible.map((project) => (
                  <li
                    key={project.id}
                    className={`studio-card${busyId === project.id ? " is-busy" : ""}${project.archived ? " is-archived" : ""}`}
                  >
                    <button
                      type="button"
                      className="studio-card-main"
                      onClick={() => openProject(project)}
                    >
                      <span className="studio-card-title">{project.title}</span>
                      <span className="studio-card-meta">{projectMeta(project)}</span>
                      <span className="studio-card-foot">
                        {project.pinned ? <Icon name="fa-thumbtack" /> : null}
                        edited {relativeTime(project.updated_at)}
                      </span>
                    </button>
                    <div className="studio-card-menu" data-studio-project-menu>
                      <button
                        type="button"
                        className="studio-card-menu-btn"
                        aria-haspopup="menu"
                        aria-expanded={menuId === project.id}
                        aria-label={`Actions for ${project.title}`}
                        onClick={() => setMenuId(menuId === project.id ? null : project.id)}
                      >
                        <Icon name="fa-ellipsis" />
                      </button>
                      {menuId === project.id ? (
                        <div className="studio-card-menu-pop" role="menu">
                          <button type="button" role="menuitem" onClick={() => openProject(project)}>
                            Open
                          </button>
                          <button
                            type="button"
                            role="menuitem"
                            onClick={() => {
                              setRenameValue(project.title);
                              setRenameTarget(project);
                              setMenuId(null);
                            }}
                          >
                            Rename
                          </button>
                          <button
                            type="button"
                            role="menuitem"
                            onClick={() => void duplicate(project)}
                          >
                            Duplicate
                          </button>
                          <button
                            type="button"
                            role="menuitem"
                            onClick={() => void togglePin(project)}
                          >
                            {project.pinned ? "Unpin" : "Pin"}
                          </button>
                          <button
                            type="button"
                            role="menuitem"
                            onClick={() => void toggleArchive(project)}
                          >
                            {project.archived ? "Restore" : "Archive"}
                          </button>
                          <button
                            type="button"
                            role="menuitem"
                            className="danger"
                            onClick={() => {
                              setDeleteTarget(project);
                              setMenuId(null);
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>

      {renameTarget ? (
        <div className="studio-dialog-backdrop" role="presentation" onClick={() => setRenameTarget(null)}>
          <div
            className="studio-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="studio-rename-title"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="studio-rename-title">Rename project</h2>
            <input
              ref={renameInputRef}
              value={renameValue}
              maxLength={120}
              onChange={(event) => setRenameValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void commitRename();
                if (event.key === "Escape") setRenameTarget(null);
              }}
              aria-label="Project title"
            />
            <div className="studio-dialog-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setRenameTarget(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void commitRename()}
                disabled={!renameValue.trim()}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {deleteTarget ? (
        <div className="studio-dialog-backdrop" role="presentation" onClick={() => setDeleteTarget(null)}>
          <div
            className="studio-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="studio-delete-title"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="studio-delete-title">Delete “{deleteTarget.title}”?</h2>
            <p>This removes the project and its saved versions. It cannot be undone.</p>
            <div className="studio-dialog-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setDeleteTarget(null)}>
                Keep project
              </button>
              <button type="button" className="btn btn-danger" onClick={() => void commitDelete()}>
                Delete
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
