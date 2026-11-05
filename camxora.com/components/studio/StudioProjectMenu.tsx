"use client";

import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import {
  createStudioProject,
  forkStudioProject,
  listStudioProjects,
  listStudioProjectVersions,
  restoreStudioProjectVersion,
  updateStudioProject,
  type StudioProject,
  type StudioProjectVersion,
} from "@/lib/studio-api";

/**
 * Project menu (reference §18.1 / §44.2).
 *
 * The captured menu is nine items. Six are wired here with the endpoints this product
 * already has; Share, v1-copy and Settings are rendered disabled with the reason in
 * their tooltip rather than hidden, so the order still matches the capture and nothing
 * pretends to work. Navigation is a full page load because the editor reads the project
 * id from the URL on mount.
 */

type Dialog = "open" | "rename" | "versions" | null;

export type StudioProjectMenuProps = {
  projectId: string;
  title: string;
  onRenamed: (title: string) => void;
  onShowQuickStart: () => void;
};

const UNTITLED = "Untitled project";

export function StudioProjectMenu({
  projectId,
  title,
  onRenamed,
  onShowQuickStart,
}: StudioProjectMenuProps) {
  const [open, setOpen] = useState(false);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [projects, setProjects] = useState<StudioProject[] | null>(null);
  const [versions, setVersions] = useState<StudioProjectVersion[] | null>(null);
  const [renameValue, setRenameValue] = useState(title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  const label = title || UNTITLED;

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

  return (
    <div className="se-project" ref={wrapperRef}>
      <button
        type="button"
        className="se-chip"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {label}
        <Icon name="fa-chevron-down" />
      </button>

      {open ? (
        <div className="se-project-menu" role="menu" aria-label="Project options">
          <button type="button" role="menuitem" onClick={startNewProject} disabled={busy}>
            New Project
          </button>
          <button type="button" role="menuitem" onClick={() => openDialog("open")} disabled={busy}>
            Open Project
          </button>
          <button type="button" role="menuitem" onClick={() => openDialog("rename")} disabled={busy}>
            Rename
          </button>
          <button type="button" role="menuitem" onClick={duplicate} disabled={busy}>
            Duplicate Project
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => openDialog("versions")}
            disabled={busy}
          >
            Version History
          </button>
          <button
            type="button"
            role="menuitem"
            disabled
            title="Sharing is not wired into the editor yet"
          >
            Share Project
          </button>
          <button
            type="button"
            role="menuitem"
            disabled
            title="There is no v1 Studio in this product"
          >
            Open a copy in v1
          </button>
          <button
            type="button"
            role="menuitem"
            disabled
            title="Studio settings are not built yet"
          >
            Studio Settings
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onShowQuickStart();
            }}
          >
            Show Quick Start again
          </button>
        </div>
      ) : null}

      {dialog ? (
        <div
          className="se-dialog-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label={
            dialog === "open" ? "Open project" : dialog === "rename" ? "Rename project" : "Version history"
          }
        >
          <div className="se-dialog">
            {dialog === "open" ? (
              <>
                <h2>Open project</h2>
                {projects === null ? (
                  <p className="se-dialog-note">Loading projects…</p>
                ) : projects.length === 0 ? (
                  <p className="se-dialog-note">No other projects yet.</p>
                ) : (
                  <ul className="se-dialog-list">
                    {projects.map((item) => (
                      <li key={item.id} className="se-dialog-row">
                        <span className="se-dialog-title">{item.title || UNTITLED}</span>
                        <button
                          type="button"
                          className="se-pill"
                          onClick={() => navigate(item.id)}
                          aria-label={`Open ${item.title || UNTITLED}`}
                        >
                          Open
                        </button>
                      </li>
                    ))}
                  </ul>
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
            ) : (
              <>
                <h2>Version history</h2>
                {versions === null ? (
                  <p className="se-dialog-note">Loading versions…</p>
                ) : versions.length === 0 ? (
                  <p className="se-dialog-note">
                    No saved versions yet. Versions are snapshots you save on purpose.
                  </p>
                ) : (
                  <ul className="se-dialog-list">
                    {versions.map((version) => (
                      <li key={version.id} className="se-dialog-row">
                        <span className="se-dialog-title">
                          {version.label || version.title || "Version"}
                        </span>
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
                    ))}
                  </ul>
                )}
                {versions !== null && versions.length > 0 ? (
                  <p className="se-dialog-note">Restoring replaces the arrangement and reloads the editor.</p>
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
              <button type="button" className="se-pill" onClick={() => setDialog(null)} disabled={busy}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
