"use client";

import Link from "next/link";

import { Icon } from "@/components/Icon";

/**
 * Studio's own top bar — Suno's Studio has its own chrome instead of the site
 * header, so Camxora Studio does the same: brand, project slot, Export, Library.
 */
export function StudioHeader({
  projectName,
  onNewProject,
  canExport = false,
}: {
  projectName?: string | null;
  onNewProject?: () => void;
  canExport?: boolean;
}) {
  return (
    <header className="st-chrome">
      <Link className="st-brand" href="/">
        <img src="/camxora-logo.svg" alt="" />
        <b>CAMXORA</b>
      </Link>
      <span className="st-chrome-project">{projectName || "No project loaded"}</span>
      <span className="st-chrome-dots">···</span>
      <span style={{ flex: 1 }} />
      {onNewProject ? (
        <button type="button" className="s-btn s-btn-ghost" onClick={onNewProject}>
          <Icon name="fa-plus" /> New project
        </button>
      ) : null}
      <button type="button" className="s-btn s-btn-ghost" disabled={!canExport}>
        <Icon name="fa-arrow-up-from-bracket" /> Export
      </button>
      <Link className="s-btn s-btn-ghost" href="/library">
        <Icon name="fa-folder-open" /> Library
      </Link>
    </header>
  );
}
