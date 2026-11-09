"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/Icon";
import { CreatorMetrics } from "@/components/CreatorMetrics";
import {
  createRelease,
  CreatorApiError,
  fetchReleases,
  submitRelease,
  unpublishRelease,
  withdrawRelease,
  type CreatorRelease,
} from "@/lib/creator-api";
import { fetchGenerations, type WebMusicGeneration } from "@/lib/library-api";

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  submitted: "In review",
  in_review: "In review",
  changes_requested: "Changes requested",
  approved: "Approved",
  scheduled: "Scheduled",
  published: "Live",
  taken_down: "Taken down",
  rejected: "Rejected",
};

function stage(status: string): number {
  if (["draft", "changes_requested", "rejected", "taken_down"].includes(status)) return 0;
  if (["submitted", "in_review", "approved", "scheduled"].includes(status)) return 1;
  return 2;
}

function ReleaseFlow({ status }: { status: string }) {
  const current = stage(status);
  const steps = ["Draft", "Review", "Live"];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
      {steps.map((step, index) => (
        <div key={step} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            aria-hidden="true"
            style={{
              width: 6,
              height: 6,
              borderRadius: 999,
              background: index <= current ? "var(--accent, #8b7cf6)" : "rgba(255,255,255,0.18)",
            }}
          />
          <span
            style={{
              fontSize: 11,
              color: index <= current ? "rgba(255,255,255,0.78)" : "rgba(255,255,255,0.38)",
            }}
          >
            {step}
          </span>
          {index < steps.length - 1 ? (
            <span
              aria-hidden="true"
              style={{
                width: 18,
                height: 1,
                background: index < current ? "rgba(139,124,246,0.55)" : "rgba(255,255,255,0.1)",
              }}
            />
          ) : null}
        </div>
      ))}
    </div>
  );
}

function formatDate(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function CreatorReleasesView() {
  const [releases, setReleases] = useState<CreatorRelease[]>([]);
  const [generations, setGenerations] = useState<WebMusicGeneration[]>([]);
  const [selected, setSelected] = useState("");
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("Khmer Pop");
  const [rights, setRights] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const readyOptions = useMemo(() => {
    return generations.flatMap((generation) =>
      (generation.clips ?? [])
        .filter((clip) => clip.ready)
        .map((clip) => ({
          value: `${generation.id}:${clip.variant}`,
          taskId: generation.id,
          variant: clip.variant as "ok" | "alt",
          title: generation.title || "Untitled",
          label: `${generation.title || "Untitled"} · ${clip.variant === "alt" ? "Version 2" : "Version 1"}`,
        }))
    );
  }, [generations]);

  async function refresh() {
    const releaseData = await fetchReleases();
    setReleases(releaseData.items);
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([fetchReleases(), fetchGenerations(60)])
      .then(([releaseData, generationData]) => {
        if (!active) return;
        setReleases(releaseData.items);
        setGenerations(generationData);
      })
      .catch((cause) => {
        if (!active) return;
        if (cause instanceof CreatorApiError && cause.status === 401) {
          setUnauthorized(true);
        } else {
          setError(cause instanceof Error ? cause.message : "Could not load releases");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function onSelect(value: string) {
    setSelected(value);
    const option = readyOptions.find((item) => item.value === value);
    if (option && !title.trim()) setTitle(option.title);
  }

  async function onCreate(event: React.FormEvent) {
    event.preventDefault();
    const option = readyOptions.find((item) => item.value === selected);
    if (!option) {
      setError("Pick a finished generation first.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await createRelease({
        source_task_id: option.taskId,
        variant: option.variant,
        metadata: {
          title: title.trim(),
          genre: genre.trim(),
          genres: [genre.trim()],
          language: "km",
          release_type: "single",
          rights_attested: rights,
        },
      });
      setSuccess("Draft created. Add it to review when you are ready.");
      setSelected("");
      setTitle("");
      setRights(false);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create release");
    } finally {
      setSaving(false);
    }
  }

  async function onAction(release: CreatorRelease) {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      if (["draft", "changes_requested"].includes(release.status)) {
        await submitRelease(release.id);
        setSuccess("Release submitted for review.");
      } else if (["submitted", "in_review"].includes(release.status)) {
        await withdrawRelease(release.id);
        setSuccess("Release returned to draft.");
      } else if (release.status === "published") {
        await unpublishRelease(release.id);
        setSuccess("Release taken down.");
      }
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update release");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="page"><p className="fine" style={{ textAlign: "left" }}>Loading releases…</p></div>;
  }

  if (unauthorized) {
    return (
      <div className="page">
        <div className="invite-signin panel">
          <span className="invite-hero-icon"><Icon name="fa-record-vinyl" /></span>
          <h1>Releases</h1>
          <p>Sign in to move a generation from draft to live.</p>
          <Link className="btn btn-primary" href="/login?next=/creator/releases">Sign in</Link>
        </div>
      </div>
    );
  }

  const drafts = releases.filter((item) => ["draft", "changes_requested"].includes(item.status)).length;
  const inReview = releases.filter((item) => ["submitted", "in_review", "approved", "scheduled"].includes(item.status)).length;
  const live = releases.filter((item) => item.status === "published").length;

  return (
    <div className="page">
      <header style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 16, marginBottom: 24 }}>
        <div>
          <p className="fine" style={{ margin: 0 }}>Creator Studio</p>
          <h1 style={{ margin: "4px 0 8px" }}>Releases</h1>
          <p style={{ margin: 0 }}>Move a finished generation from draft to live on Camxora.</p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/creator">Back to Studio</Link>
          <Link className="btn btn-ghost" href="/create">Create music</Link>
        </div>
      </header>

      {error ? <p className="fine" style={{ color: "#f87171" }} role="alert">{error}</p> : null}
      {success ? <p className="fine" style={{ color: "#4ade80" }} role="status">{success}</p> : null}

      <CreatorMetrics
        items={[
          { label: "Drafts", value: drafts },
          { label: "In review", value: inReview },
          { label: "Live", value: live },
          { label: "Total", value: releases.length },
        ]}
      />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 24, alignItems: "start" }}>
        <section className="panel">
          <div className="sec-head"><h2>New release</h2></div>
          {readyOptions.length === 0 ? (
            <div>
              <p style={{ marginTop: 0 }}>No finished generations yet.</p>
              <p className="fine" style={{ textAlign: "left" }}>Create a track, wait for it to finish, then come back here.</p>
              <Link className="btn btn-ghost" href="/create">Create music</Link>
            </div>
          ) : (
            <form onSubmit={onCreate} style={{ display: "grid", gap: 16 }}>
              <div className="auth-field">
                <label htmlFor="release-generation">Finished generation</label>
                <select
                  id="release-generation"
                  className="auth-input"
                  value={selected}
                  onChange={(event) => onSelect(event.target.value)}
                  required
                >
                  <option value="">Choose a generation</option>
                  {readyOptions.map((option) => (
                    <option value={option.value} key={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div className="auth-field">
                <label htmlFor="release-title">Title</label>
                <input
                  id="release-title"
                  className="auth-input"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  maxLength={100}
                  required
                />
              </div>
              <div className="auth-field">
                <label htmlFor="release-genre">Genre</label>
                <input
                  id="release-genre"
                  className="auth-input"
                  value={genre}
                  onChange={(event) => setGenre(event.target.value)}
                  maxLength={120}
                  required
                />
              </div>
              <label style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <input
                  type="checkbox"
                  checked={rights}
                  onChange={(event) => setRights(event.target.checked)}
                  required
                />
                <span className="fine">I own or have cleared the rights to this track.</span>
              </label>
              <div>
                <button className="btn btn-primary" type="submit" disabled={saving || !selected || !rights}>
                  {saving ? "Creating…" : "Create draft"}
                </button>
              </div>
            </form>
          )}
        </section>

        <section className="panel">
          <div className="sec-head">
            <h2>Your releases</h2>
            <span className="fine">{releases.length} total</span>
          </div>
          {releases.length === 0 ? (
            <p className="fine" style={{ textAlign: "left" }}>No releases yet. Create a draft to start.</p>
          ) : (
            <div>
              {releases.map((release, index) => {
                const metadata = release.metadata || {};
                const canSubmit = ["draft", "changes_requested"].includes(release.status);
                const canWithdraw = ["submitted", "in_review"].includes(release.status);
                const canUnpublish = release.status === "published";
                return (
                  <article
                    key={release.id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "minmax(0, 1fr) auto",
                      gap: 16,
                      padding: "16px 0",
                      borderTop: index === 0 ? "none" : "1px solid rgba(255,255,255,0.06)",
                      alignItems: "start",
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 10 }}>
                        <strong style={{ fontSize: 15 }}>{metadata.title || "Untitled"}</strong>
                        <span className="fine" style={{ margin: 0 }}>{STATUS_LABEL[release.status] || release.status}</span>
                      </div>
                      <p className="fine" style={{ margin: "4px 0 0", textAlign: "left" }}>
                        {metadata.genre || "No genre"} · {metadata.release_type || "single"}
                        {release.submitted_at ? ` · submitted ${formatDate(release.submitted_at)}` : ""}
                      </p>
                      <ReleaseFlow status={release.status} />
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                      {canSubmit ? (
                        <button className="btn btn-ghost" type="button" onClick={() => onAction(release)} disabled={saving}>
                          Submit
                        </button>
                      ) : null}
                      {canWithdraw ? (
                        <button className="btn btn-ghost" type="button" onClick={() => onAction(release)} disabled={saving}>
                          Withdraw
                        </button>
                      ) : null}
                      {canUnpublish ? (
                        <button className="btn btn-ghost" type="button" onClick={() => onAction(release)} disabled={saving}>
                          Unpublish
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>

      <section className="panel" style={{ marginTop: 24 }}>
        <div className="sec-head">
          <h2>How releases work</h2>
          <span className="fine">Review takes up to 3 business days</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 24 }}>
          <div>
            <p className="fine" style={{ margin: 0 }}>01</p>
            <strong style={{ display: "block", margin: "4px 0" }}>Pick a finished generation</strong>
            <p className="fine" style={{ margin: 0, textAlign: "left" }}>Only tracks with stored audio can be submitted.</p>
          </div>
          <div>
            <p className="fine" style={{ margin: 0 }}>02</p>
            <strong style={{ display: "block", margin: "4px 0" }}>Send it to review</strong>
            <p className="fine" style={{ margin: 0, textAlign: "left" }}>We check rights, metadata, and audio readiness.</p>
          </div>
          <div>
            <p className="fine" style={{ margin: 0 }}>03</p>
            <strong style={{ display: "block", margin: "4px 0" }}>Go live</strong>
            <p className="fine" style={{ margin: 0, textAlign: "left" }}>Approved releases appear on your creator page and in the catalog.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
