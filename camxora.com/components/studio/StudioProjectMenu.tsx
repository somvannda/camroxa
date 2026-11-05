"use client";

import { useEffect, useRef, useState } from "react";

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

/**
 * Project menu (reference §18.1 / §44.2 / §24).
 *
 * The captured menu is nine items. Seven are wired here with the endpoints this product
 * already has; the v1 copy and Settings are rendered disabled with the reason in their
 * tooltip rather than hidden, so the order still matches the capture and nothing
 * pretends to work. Navigation is a full page load because the editor reads the project
 * id from the URL on mount.
 *
 * Sharing follows the captured semantics (§24): a link is view + fork, never live
 * co-editing, and an unnamed project hits a naming gate first (§24.1).
 */

type Dialog = "open" | "rename" | "versions" | "share" | "name-to-share" | null;

export type StudioProjectMenuProps = {
  projectId: string;
  title: string;
  onRenamed: (title: string) => void;
  onShowQuickStart: () => void;
};

const UNTITLED = "Untitled project";

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
  onRenamed,
  onShowQuickStart,
}: StudioProjectMenuProps) {
  const [open, setOpen] = useState(false);
  const [dialog, setDialog] = useState<Dialog>(null);
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
          <button type="button" role="menuitem" onClick={startSharing} disabled={busy}>
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
            dialog === "open"
              ? "Open project"
              : dialog === "rename"
                ? "Rename project"
                : dialog === "versions"
                  ? "Version history"
                  : dialog === "share"
                    ? "Share project"
                    : "Name project before sharing"
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
            ) : dialog === "versions" ? (
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
            ) : (
              <>
                <h2>Share “{shareName}”</h2>
                <p className="se-dialog-note">
                  Anyone with the link can view this project and make their own editable copy. Your
                  project stays as it is — they cannot edit or change your version.
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
              {dialog === "open" || dialog === "versions" ? (
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
