"use client";

import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/Icon";
import { CreatorMetrics } from "@/components/CreatorMetrics";
import {
  CreatorButton,
  CreatorButtonLink,
  CreatorCheckbox,
  CreatorField,
  CreatorHeader,
  CreatorInput,
  CreatorPage,
  CreatorPanel,
  CreatorSelect,
  CreatorStatus,
  CreatorToast,
  useCreatorToast,
} from "@/components/CreatorUI";
import styles from "@/components/creator-ui.module.css";
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
  return 1;
}

function statusTone(status: string): "neutral" | "review" | "live" | "danger" {
  if (status === "published") return "live";
  if (["submitted", "in_review", "changes_requested"].includes(status)) return "review";
  if (["rejected", "taken_down"].includes(status)) return "danger";
  return "neutral";
}

function ReleaseFlow({ status }: { status: string }) {
  const current = stage(status);
  const steps = ["Draft", "Live"];
  return (
    <div className={styles.flow}>
      {steps.map((step, index) => (
        <div className={styles.flowStep} key={step}>
          <span
            aria-hidden="true"
            className={`${styles.flowDot} ${index <= current ? styles.flowDotActive : ""}`}
          />
          <span className={`${styles.flowLabel} ${index <= current ? styles.flowLabelActive : ""}`}>
            {step}
          </span>
          {index < steps.length - 1 ? (
            <span
              aria-hidden="true"
              className={`${styles.flowLine} ${index < current ? styles.flowLineActive : ""}`}
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
  const { toast, showToast, dismiss } = useCreatorToast();

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
      showToast("Draft created. Add it to review when you are ready.");
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
    try {
      if (["draft", "changes_requested"].includes(release.status)) {
        await submitRelease(release.id);
        showToast("Published. Your release is live on Camxora.");
      } else if (["submitted", "in_review"].includes(release.status)) {
        await withdrawRelease(release.id);
        showToast("Release returned to draft.");
      } else if (release.status === "published") {
        await unpublishRelease(release.id);
        showToast("Release taken down.");
      }
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not update release");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Creator Studio" title="Releases" />
        <div className={styles.skeletonPanel}>
          <div className={styles.skeleton} style={{ width: 220, height: 28 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 72 }} />
          <div className={styles.skeleton} style={{ width: "100%", height: 260 }} />
        </div>
      </CreatorPage>
    );
  }

  if (unauthorized) {
    return (
      <CreatorPage>
        <CreatorHeader meta="Creator Studio" title="Releases" />
        <CreatorPanel>
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>Sign in to manage releases</p>
            <p className={styles.emptyBody}>Move a finished generation from draft to live.</p>
            <div>
              <CreatorButtonLink href="/login?next=/creator/releases" variant="primary">
                <Icon name="fa-right-to-bracket" /> Sign in
              </CreatorButtonLink>
            </div>
          </div>
        </CreatorPanel>
      </CreatorPage>
    );
  }

  const drafts = releases.filter((item) => ["draft", "changes_requested"].includes(item.status)).length;
  const inReview = releases.filter((item) => ["submitted", "in_review", "approved", "scheduled"].includes(item.status)).length;
  const live = releases.filter((item) => item.status === "published").length;

  return (
    <CreatorPage>
      <CreatorHeader
        meta="Creator Studio"
        title="Releases"
        description="Move a finished generation from draft to live on Camxora."
        actions={
          <>
            <CreatorButtonLink href="/creator" variant="ghost">
              <Icon name="fa-arrow-left" /> Back to Studio
            </CreatorButtonLink>
            <CreatorButtonLink href="/create" variant="ghost">
              <Icon name="fa-plus" /> Create music
            </CreatorButtonLink>
          </>
        }
      />

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <CreatorMetrics
        items={[
          { label: "Drafts", value: drafts },
          { label: "In review", value: inReview },
          { label: "Live", value: live },
          { label: "Total", value: releases.length },
        ]}
      />

      <div className={styles.split}>
        <CreatorPanel title="New release">
          {readyOptions.length === 0 ? (
            <div className={styles.empty}>
              <p className={styles.emptyTitle}>No finished generations yet</p>
              <p className={styles.emptyBody}>Create a track, wait for it to finish, then come back here.</p>
              <div>
                <CreatorButtonLink href="/create" variant="secondary">
                  <Icon name="fa-plus" /> Create music
                </CreatorButtonLink>
              </div>
            </div>
          ) : (
            <form className={styles.form} onSubmit={onCreate}>
              <CreatorField label="Finished generation" htmlFor="release-generation">
                <CreatorSelect
                  id="release-generation"
                  value={selected}
                  onValueChange={onSelect}
                  options={readyOptions.map((option) => ({
                    value: option.value,
                    label: option.label,
                  }))}
                  placeholder="Choose a generation"
                  ariaLabel="Finished generation"
                />
              </CreatorField>
              <CreatorField label="Title" htmlFor="release-title">
                <CreatorInput
                  id="release-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  maxLength={100}
                  required
                />
              </CreatorField>
              <CreatorField label="Genre" htmlFor="release-genre">
                <CreatorInput
                  id="release-genre"
                  value={genre}
                  onChange={(event) => setGenre(event.target.value)}
                  maxLength={120}
                  required
                />
              </CreatorField>
              <CreatorCheckbox
                id="release-rights"
                checked={rights}
                onCheckedChange={setRights}
                label="I own or have cleared the rights to this track."
              />
              <div>
                <CreatorButton type="submit" disabled={saving || !selected || !rights}>
                  <Icon name="fa-plus" /> {saving ? "Creating…" : "Create draft"}
                </CreatorButton>
              </div>
            </form>
          )}
        </CreatorPanel>

        <CreatorPanel title="Your releases" meta={`${releases.length} total`}>
          {releases.length === 0 ? (
            <div className={styles.empty}>
              <p className={styles.emptyTitle}>No releases yet</p>
              <p className={styles.emptyBody}>Create a draft to start the review flow.</p>
            </div>
          ) : (
            <div className={styles.list}>
              {releases.map((release) => {
                const metadata = release.metadata || {};
                const canSubmit = ["draft", "changes_requested"].includes(release.status);
                const canWithdraw = ["submitted", "in_review"].includes(release.status);
                const canUnpublish = release.status === "published";
                return (
                  <article className={styles.row} key={release.id}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 10 }}>
                        <p className={styles.rowTitle}>{metadata.title || "Untitled"}</p>
                        <CreatorStatus
                          label={STATUS_LABEL[release.status] || release.status}
                          tone={statusTone(release.status)}
                        />
                      </div>
                      <p className={styles.rowMeta}>
                        {metadata.genre || "No genre"} · {metadata.release_type || "single"}
                        {release.submitted_at ? ` · submitted ${formatDate(release.submitted_at)}` : ""}
                      </p>
                      <ReleaseFlow status={release.status} />
                    </div>
                    <div className={styles.rowActions}>
                      {canSubmit ? (
                        <CreatorButton variant="secondary" type="button" onClick={() => onAction(release)} disabled={saving}>
                          <Icon name="fa-paper-plane" /> Publish
                        </CreatorButton>
                      ) : null}
                      {canWithdraw ? (
                        <CreatorButton variant="secondary" type="button" onClick={() => onAction(release)} disabled={saving}>
                          <Icon name="fa-rotate-left" /> Withdraw
                        </CreatorButton>
                      ) : null}
                      {canUnpublish ? (
                        <CreatorButton variant="secondary" type="button" onClick={() => onAction(release)} disabled={saving}>
                          <Icon name="fa-eye-slash" /> Unpublish
                        </CreatorButton>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </CreatorPanel>
      </div>

      <CreatorPanel title="How releases work" meta="Published instantly · reviewed after" className={styles.sectionGap}>
        <div className={styles.guideGrid}>
          <div className={styles.guideStep}>
            <p className={styles.guideNumber}>01</p>
            <p className={styles.guideTitle}>Pick a finished generation</p>
            <p className={styles.guideBody}>Only tracks with stored audio can be published.</p>
          </div>
          <div className={styles.guideStep}>
            <p className={styles.guideNumber}>02</p>
            <p className={styles.guideTitle}>Publish instantly</p>
            <p className={styles.guideBody}>Automated checks cover rights, metadata, and audio readiness.</p>
          </div>
          <div className={styles.guideStep}>
            <p className={styles.guideNumber}>03</p>
            <p className={styles.guideTitle}>Review after publish</p>
            <p className={styles.guideBody}>Reports and spot checks can take a release down later.</p>
          </div>
        </div>
      </CreatorPanel>
      <CreatorToast toast={toast} onDismiss={dismiss} />
    </CreatorPage>
  );
}
