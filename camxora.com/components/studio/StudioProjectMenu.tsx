"use client";

import { useEffect, useRef, useState, useMemo } from "react";

import { Icon } from "@/components/Icon";
import {
  createStudioProject,
  createStudioProjectShare,
  forkStudioProject,
  listStudioProjectShares,
  listStudioProjects,
  listStudioProjectVersions,
  restoreStudioProjectVersion,
  updateStudioProject,
  type StudioProject,
  type StudioProjectShare,
  type StudioProjectVersion,
} from "@/lib/studio-api";
import type { StudioSettings } from "@/lib/studio-settings";

/**
 * Project menu (reference §18.1 / §44.2 / §24).
 *
 * The captured menu is nine items. Eight are wired here with the endpoints this product
 * already has; the v1 copy is rendered disabled with the reason in its tooltip rather
 * than hidden, so the order still matches the capture and nothing pretends to work.
 * Navigation is a full page load because the editor reads the project id from the URL
 * on mount.
 *
 * Sharing follows the captured semantics (§24): a link is view + fork, never live
 * co-editing, and an unnamed project hits a naming gate first (§24.1). Settings shows
 * only the one captured setting (§22).
 */

type Dialog =
  | "open"
  | "rename"
  | "versions"
  | "share"
  | "name-to-share"
  | "settings"
  | null;

export type StudioProjectMenuProps = {
  projectId: string;
  title: string;
  settings: StudioSettings;
  onSettingsChange: (next: StudioSettings) => void;
  onRenamed: (title: string) => void;
  onShowQuickStart: () => void;
};

const UNTITLED = "Untitled project";

const initialOf = (value: string) => (value.trim()[0] || "P").toUpperCase();

function isUnnamed(value: string): boolean {
  const trimmed = value.trim();
  return trimmed.length === 0 || trimmed.toLowerCase() === UNTITLED.toLowerCase();
}

/** Prefer an existing live link over minting a second one for the same project. */
function liveShare(shares: StudioProjectShare[]): StudioProjectShare | null {
  const now = Date.now();
  return (
    shares.find((share) => {
      if (share.revoked_at) return false;
      if (share.active === false) return false;
      if (!share.expires_at) return true;
      const expires = Date.parse(share.expires_at);
      return Number.isNaN(expires) || expires > now;
    }) ?? null
  );
}

export function StudioProjectMenu({
  projectId,
  title,
  settings,
  onSettingsChange,
  onRenamed,
  onShowQuickStart,
}: StudioProjectMenuProps) {
  const [open, setOpen] = useState(false);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [projectTab, setProjectTab] = useState<"projects" | "deleted">("projects");
  const [projectQuery, setProjectQuery] = useState("");
  const [projectSort, setProjectSort] = useState<"newest" | "oldest">("newest");
  const [projects, setProjects] = useState<StudioProject[] | null>(null);
  const [versions, setVersions] = useState<StudioProjectVersion[] | null>(null);
  const [renameValue, setRenameValue] = useState(title);
  const [gateValue, setGateValue] = useState(title);
  const [share, setShare] = useState<StudioProjectShare | null>(null);
  const [shareName, setShareName] = useState(title);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const label = title || UNTITLED;
  const shareUrl =
    share && typeof window !== "undefined" ? `${window.location.origin}${share.path}` : "";

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const onPointer = (event: PointerEvent) => {
      const node = wrapperRef.current;
      if (node && !node.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  useEffect(() => {
    setRenameValue(title);
  }, [title]);

  // `ctrl shift ,` opens Studio Settings, the accelerator the capture records (§18.1).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!event.ctrlKey || !event.shiftKey || event.key !== ",") return;
      // Do not stack Settings on top of another dialog the user is already in.
      if (dialog !== null) return;
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      setOpen(false);
      setError("");
      setDialog("settings");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dialog]);

  function navigate(id: string) {
    window.location.href = `/studio/editor?project=${encodeURIComponent(id)}`;
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That action failed.");
    } finally {
      setBusy(false);
    }
  }

  function openDialog(next: Exclude<Dialog, null>) {
    setOpen(false);
    setError("");
    setDialog(next);
    if (next === "open") {
      setProjects(null);
      listStudioProjects(20, 0, false)
        .then((result) => setProjects(result.items ?? []))
        .catch(() => setProjects([]));
    }
    if (next === "versions") {
      setVersions(null);
      listStudioProjectVersions(projectId)
        .then((result) => setVersions(result.items ?? []))
        .catch(() => setVersions([]));
    }
    if (next === "rename") setRenameValue(title);
  }

  function startNewProject() {
    setOpen(false);
    void run(async () => {
      const created = await createStudioProject({
        title: UNTITLED,
        bpm: 120,
        time_signature: "4/4",
        data: {},
      });
      navigate(created.id);
    });
  }

  function duplicate() {
    setOpen(false);
    void run(async () => {
      const copy = await forkStudioProject(projectId, `${label} copy`);
      navigate(copy.id);
    });
  }

  function submitRename() {
    const next = renameValue.trim();
    if (!next) {
      setError("A project title is required.");
      return;
    }
    void run(async () => {
      const updated = await updateStudioProject(projectId, { title: next });
      onRenamed(updated.title || next);
      setDialog(null);
    });
  }

  function restore(versionId: string) {
    void run(async () => {
      await restoreStudioProjectVersion(projectId, versionId);
      // The restored document replaces the arrangement; reload so the editor re-reads it.
      window.location.reload();
    });
  }

  /** Open the share surface, through the naming gate when the project is unnamed. */
  function startSharing() {
    setOpen(false);
    if (isUnnamed(title)) {
      setGateValue(title.trim() || UNTITLED);
      setDialog("name-to-share");
      return;
    }
    void openShare(title);
  }

  async function openShare(name: string) {
    setShareName(name.trim() || UNTITLED);
    setShare(null);
    setCopyState("idle");
    setDialog("share");
    await run(async () => {
      const existing = await listStudioProjectShares(projectId).catch(() => ({ items: [] }));
      const found = liveShare(existing.items ?? []);
      if (found) {
        setShare(found);
        return;
      }
      const created = await createStudioProjectShare(projectId, 7, "view");
      setShare(created);
    });
  }

  function saveNameThenShare() {
    const next = gateValue.trim();
    if (!next) {
      setError("A project title is required.");
      return;
    }
    void run(async () => {
      const updated = await updateStudioProject(projectId, { title: next });
      const name = updated.title || next;
      onRenamed(name);
      await openShare(name);
    });
  }

  async function copyLink() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  /** Version list grouped under a date heading, like the captured History panel. */
  const [historyDay, setHistoryDay] = useState(0);
  useEffect(() => {
    if (dialog !== "versions") setHistoryDay(0);
  }, [dialog]);

  const groupedVersions = useMemo(() => {
    const map = new Map<string, StudioProjectVersion[]>();
    for (const version of versions ?? []) {
      const date = version.created_at ? new Date(version.created_at) : null;
      const day =
        date && !Number.isNaN(date.getTime()) ? date.toLocaleDateString() : "Unknown date";
      const list = map.get(day);
      if (list) list.push(version);
      else map.set(day, [version]);
    }
    return [...map.entries()];
  }, [versions]);

  return (
    <div className="se-project" ref={wrapperRef}>
      <button
        type="button"
        className="se-chip"
        aria-haspopup="menu"
        aria-expanded={open}
        data-help="project"
        onClick={() => setOpen((value) => !value)}
      >
        {label}
        <Icon name="fa-ellipsis" />
      </button>

      {open ? (
        <div className="se-project-menu" role="menu" aria-label="Project options">
          <button type="button" role="menuitem" onClick={startNewProject} disabled={busy}>
            <Icon name="fa-plus" /> New Project
          </button>
          <button type="button" role="menuitem" onClick={() => openDialog("open")} disabled={busy}>
            <Icon name="fa-folder-open" /> Open Project
          </button>
          <button type="button" role="menuitem" onClick={() => openDialog("rename")} disabled={busy}>
            <Icon name="fa-pen" /> Rename
          </button>
          <button type="button" role="menuitem" onClick={duplicate} disabled={busy}>
            <Icon name="fa-copy" /> Duplicate Project
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => openDialog("versions")}
            disabled={busy}
          >
            <Icon name="fa-clock-rotate-left" /> Version History
          </button>
          <button type="button" role="menuitem" onClick={startSharing} disabled={busy}>
            <Icon name="fa-arrow-up-from-bracket" /> Share Project
          </button>
          <button
            type="button"
            role="menuitem"
            disabled
            title="There is no v1 Studio in this product"
          >
            <Icon name="fa-box-archive" /> Open a copy in v1
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => openDialog("settings")}
            disabled={busy}
          >
            <Icon name="fa-gear" /> Studio Settings{" "}
            <span className="se-project-hint">ctrl shift ,</span>
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onShowQuickStart();
            }}
          >
            <Icon name="fa-wand-magic-sparkles" /> Show Quick Start again
          </button>
        </div>
      ) : null}

      {dialog === "versions" ? (
        <aside
          className="se-history"
          role="dialog"
          aria-modal="false"
          aria-label="Version history"
        >
          <header className="se-history-head">
            <strong>History</strong>
            <button
              type="button"
              className="se-icon"
              aria-label="Close version history"
              onClick={() => setDialog(null)}
            >
              <Icon name="fa-xmark" />
            </button>
          </header>
          <p className="se-history-note">Projects are saved automatically.</p>
          {versions === null ? (
            <p className="se-dialog-note">Loading versions…</p>
          ) : versions.length === 0 ? (
            <p className="se-dialog-note">
              No versions yet. Versions are captured automatically as you edit.
            </p>
          ) : (
            <div className="se-history-list">
              {(() => {
                const dayIndex = Math.min(historyDay, groupedVersions.length - 1);
                const [day, items] = groupedVersions[dayIndex];
                return (
                  <section key={day}>
                    <div className="se-history-stepper">
                      <button
                        type="button"
                        aria-label="Previous day"
                        disabled={dayIndex === 0}
                        onClick={() => setHistoryDay(dayIndex - 1)}
                      >
                        <Icon name="fa-chevron-left" />
                      </button>
                      <span>{day}</span>
                      <button
                        type="button"
                        aria-label="Next day"
                        disabled={dayIndex >= groupedVersions.length - 1}
                        onClick={() => setHistoryDay(dayIndex + 1)}
                      >
                        <Icon name="fa-chevron-right" />
                      </button>
                    </div>
                    <ul>
                    {items.map((version) => {
                      const at = version.created_at ? new Date(version.created_at) : null;
                      const time =
                        at && !Number.isNaN(at.getTime())
                          ? at.toLocaleTimeString()
                          : version.label || version.title || "Version";
                      return (
                        <li key={version.id} className="se-history-row">
                          <span>{version.label || time}</span>
                          <button
                            type="button"
                            className="se-pill"
                            onClick={() => restore(version.id)}
                            disabled={busy}
                            aria-label={`Restore ${version.label || version.title || "version"}`}
                          >
                            Restore
                          </button>
                        </li>
                      );
                      })}
                    </ul>
                  </section>
                );
              })()}
            </div>
          )}
          <p className="se-history-note">
            Restoring replaces the arrangement and reloads the editor.
          </p>
        </aside>
      ) : dialog ? (
        <div
          className="se-dialog-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label={
            dialog === "open"
              ? "Open project"
              : dialog === "rename"
                ? "Rename project"
                : dialog === "share"
                  ? "Share project"
                  : dialog === "name-to-share"
                    ? "Name project before sharing"
                    : "Studio settings"
          }
        >
          <div className={`se-dialog${dialog === "open" ? " se-projects-dialog" : ""}`}>
            {dialog === "open" ? (
              <>
                <header className="se-projects-head">
                  <h2>My Projects</h2>
                  <button
                    type="button"
                    className="se-icon"
                    aria-label="Close projects"
                    onClick={() => setDialog(null)}
                  >
                    <Icon name="fa-xmark" />
                  </button>
                </header>

                <div className="se-projects-tabs" role="tablist" aria-label="Project lists">
                  {(["projects", "deleted"] as const).map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      role="tab"
                      aria-selected={projectTab === tab}
                      className={projectTab === tab ? "on" : ""}
                      onClick={() => setProjectTab(tab)}
                    >
                      {tab === "projects" ? "Projects" : "Recently Deleted"}
                    </button>
                  ))}
                </div>

                {projectTab === "deleted" ? (
                  <p className="se-dialog-note">
                    Deleted projects are not kept in this build, so there is nothing to restore.
                  </p>
                ) : (
                  <>
                    <div className="se-projects-tools">
                      <label className="se-projects-search">
                        <Icon name="fa-magnifying-glass" />
                        <input
                          value={projectQuery}
                          onChange={(event) => setProjectQuery(event.target.value)}
                          placeholder="Search for Project"
                          aria-label="Search projects"
                        />
                      </label>
                      <button
                        type="button"
                        className="se-projects-sort"
                        disabled
                        title="Project filters are not built"
                      >
                        <Icon name="fa-filter" /> Filters
                      </button>
                      <select
                        className="se-projects-sort"
                        aria-label="Sort projects"
                        value={projectSort}
                        onChange={(event) =>
                          setProjectSort(event.target.value === "oldest" ? "oldest" : "newest")
                        }
                      >
                        <option value="newest">Newest First</option>
                        <option value="oldest">Oldest First</option>
                      </select>
                    </div>

                    {(() => {
                      if (projects === null) {
                        return <p className="se-dialog-note">Loading projects</p>;
                      }
                      const needle = projectQuery.trim().toLowerCase();
                      const visible = projects
                        .filter((item) => !needle || item.title?.toLowerCase().includes(needle))
                        .slice()
                        .sort((a, b) => {
                          const at = new Date(a.updated_at || a.created_at || 0).getTime();
                          const bt = new Date(b.updated_at || b.created_at || 0).getTime();
                          return projectSort === "newest" ? bt - at : at - bt;
                        });
                      return (
                        <div className="se-projects-grid">
                          <button
                            type="button"
                            className="se-project-card is-new"
                            onClick={startNewProject}
                            disabled={busy}
                          >
                            <Icon name="fa-plus" />
                            <span>New Project</span>
                          </button>
                          {visible.map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              className="se-project-card"
                              onClick={() => navigate(item.id)}
                              aria-label={`Open ${item.title || UNTITLED}`}
                            >
                              <span className="se-project-preview" aria-hidden="true">
                                <span />
                              </span>
                              <span className="se-project-meta">
                                <span className="se-project-thumb" aria-hidden="true">
                                  {initialOf(item.title || UNTITLED)}
                                </span>
                                <span className="se-project-text">
                                  <strong>{item.title || UNTITLED}</strong>
                                  <small>
                                    {item.updated_at
                                      ? new Date(item.updated_at).toLocaleDateString()
                                      : "No date"}
                                  </small>
                                </span>
                              </span>
                            </button>
                          ))}
                          {visible.length === 0 ? (
                            <p className="se-dialog-note">No projects match that search.</p>
                          ) : null}
                        </div>
                      );
                    })()}
                  </>
                )}
              </>
            ) : dialog === "rename" ? (
              <>
                <h2>Rename project</h2>
                <label className="se-dialog-note" htmlFor="se-project-title">
                  Project title
                </label>
                <input
                  id="se-project-title"
                  className="se-pill"
                  value={renameValue}
                  onChange={(event) => setRenameValue(event.target.value)}
                  aria-label="Project title"
                />
              </>
            ) : dialog === "name-to-share" ? (
              <>
                <h2>Name project before sharing</h2>
                <p className="se-dialog-note">Give your project a name before it is shared with others.</p>
                <input
                  className="se-pill"
                  value={gateValue}
                  onChange={(event) => setGateValue(event.target.value)}
                  aria-label="Project title"
                />
              </>
            ) : dialog === "settings" ? (
              <>
                <h2>Studio settings</h2>
                <section className="se-settings-section">
                  <h3>Performance</h3>
                  <label className="se-dialog-row">
                    <input
                      type="checkbox"
                      checked={settings.ghostDrag}
                      onChange={(event) =>
                        onSettingsChange({ ...settings, ghostDrag: event.target.checked })
                      }
                    />
                    <span className="se-dialog-title">Ghost drag for arrangement moves</span>
                  </label>
                  <p className="se-dialog-note">
                    On, moving a clip keeps playing the pre-drag arrangement and applies the new
                    position once when you drop it. Off, every move is applied to the engine live.
                    The setting is read when the drag starts.
                  </p>
                </section>
                <section className="se-settings-section">
                  <h3>Window management</h3>
                  <p className="se-dialog-note">Not captured yet.</p>
                </section>
                <section className="se-settings-section">
                  <h3>Content</h3>
                  <p className="se-dialog-note">Not captured yet.</p>
                </section>
              </>
            ) : (
              <>
                <h2>Share “{shareName}”</h2>
                <p className="se-dialog-lead">
                  Anyone with the link can view this project and make their own editable copy.
                </p>
                <p className="se-dialog-note">
                  Your project stays as it is — they cannot edit or change your version.
                </p>
                {share ? (
                  <>
                    <input
                      className="se-pill"
                      value={shareUrl}
                      readOnly
                      aria-label="Share link"
                      onFocus={(event) => event.currentTarget.select()}
                    />
                    <p className="se-dialog-note">
                      The link is view-and-copy only; it is not live collaboration. It expires in 7
                      days.
                    </p>
                  </>
                ) : (
                  <p className="se-dialog-note">Creating the link…</p>
                )}
                {copyState === "failed" ? (
                  <p className="se-dialog-error">Could not reach the clipboard — select and copy the link above.</p>
                ) : null}
              </>
            )}

            {error ? <p className="se-dialog-error">{error}</p> : null}

            <div className="se-dialog-foot">
              {dialog === "rename" ? (
                <button type="button" className="se-pill on" onClick={submitRename} disabled={busy}>
                  {busy ? "Saving…" : "Save"}
                </button>
              ) : null}
              {dialog === "name-to-share" ? (
                <>
                  <button
                    type="button"
                    className="se-pill"
                    onClick={() => void openShare(title)}
                    disabled={busy}
                  >
                    Skip
                  </button>
                  <button type="button" className="se-pill on" onClick={saveNameThenShare} disabled={busy}>
                    {busy ? "Saving…" : "Save"}
                  </button>
                </>
              ) : null}
              {dialog === "share" ? (
                <>
                  <button
                    type="button"
                    className="se-pill"
                    onClick={() => setDialog(null)}
                    disabled={busy}
                  >
                    Done
                  </button>
                  <button
                    type="button"
                    className="se-pill on"
                    onClick={() => void copyLink()}
                    disabled={!shareUrl || busy}
                  >
                    {copyState === "copied" ? "Copied" : "Copy Link"}
                  </button>
                </>
              ) : null}
              {dialog === "settings" ? (
                <button type="button" className="se-pill" onClick={() => setDialog(null)} disabled={busy}>
                  Close
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
