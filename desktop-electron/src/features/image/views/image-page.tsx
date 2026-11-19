import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { formatCount } from "../../../lib/format";
import { apiRequest, errorMessage } from "../../../lib/api";
import { Button } from "../../../components/button";
import { Card } from "../../../components/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
} from "../../../components/dialog";
import { PageHeader } from "../../../components/page-header";
import { Badge, StatusDot } from "../../../components/status";
import { Table, TBody, TD, TH, THead, TR } from "../../../components/table";
import { toast } from "../../../components/toast";
import {
  basenameOrDash,
  buildFooterDetail,
  buildQueueRows,
  emptyQueueMessage,
  filterBatchesByDate,
  filterJobsByBatchIds,
  formatJobStatus,
  normalizeImagePrompts,
  previewCandidates,
  splitFooterDetail,
  statusTone,
  summarizeQueue,
  todayYmd,
} from "../image-model";
import type { StatusTone } from "../image-model";
import { ImagePreviewCard, useImagePreview } from "../image-preview";
import type { ImageJobListItem } from "../image-types";
import { useImageWorkspace } from "../use-image-workspace";

type SaveState = "idle" | "saving" | "saved" | "error";

interface Banner {
  title: string;
  detail?: string | null;
}

const LOAD_ERROR = "Unable to load the Image workspace right now.";
const SAVE_ERROR = "Unable to save image settings right now.";

function useDocumentVisible(): boolean {
  const [visible, setVisible] = useState(
    () => typeof document === "undefined" || !document.hidden,
  );
  useEffect(() => {
    const update = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);
  return visible;
}

function StatusChip({
  job,
  onRetry,
  onOpen,
  busy,
}: {
  job: ImageJobListItem | null;
  onRetry: (job: ImageJobListItem) => void;
  onOpen: (job: ImageJobListItem) => void;
  busy: boolean;
}) {
  if (!job) {
    return <span className="text-text-muted">—</span>;
  }
  const tone = statusTone(job.status);
  const normalized = String(job.status ?? "").toLowerCase();
  const actionable = normalized === "failed" || normalized === "success";
  const classes: Record<StatusTone, string> = {
    success: "border-success/30 bg-success-soft text-success",
    warning: "border-warning/30 bg-warning-soft text-warning",
    danger: "border-danger/30 bg-danger-soft text-danger",
    neutral: "border-border bg-surface-2 text-text-secondary",
  };
  const label = formatJobStatus(job.status);

  if (!actionable) {
    return (
      <span
        className={`inline-flex h-6 items-center rounded-full border px-2 text-caption ${classes[tone]}`}
      >
        {label}
      </span>
    );
  }

  return (
    <button
      type="button"
      data-testid={`image-status-${job.kind}`}
      data-job-id={job.id}
      disabled={busy}
      title={
        normalized === "failed"
          ? "Double-click to retry this job"
          : "Double-click to open the output file"
      }
      onDoubleClick={() => (normalized === "failed" ? onRetry(job) : onOpen(job))}
      onKeyDown={(event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        if (normalized === "failed") onRetry(job);
        else onOpen(job);
      }}
      className={`inline-flex h-6 cursor-pointer items-center rounded-full border px-2 text-caption disabled:cursor-wait disabled:opacity-60 ${classes[tone]}`}
    >
      {label}
    </button>
  );
}

export function ImagePage() {
  const visible = useDocumentVisible();
  const query = useImageWorkspace(visible);
  const data = query.data;

  const [fromDate, setFromDate] = useState(() => todayYmd());
  const [toDate, setToDate] = useState(() => todayYmd());
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [statusLabel, setStatusLabel] = useState("Ready");
  const [banner, setBanner] = useState<Banner | null>(null);
  const [busyJobId, setBusyJobId] = useState<string | null>(null);
  const [clearOpen, setClearOpen] = useState(false);
  const [clearing, setClearing] = useState(false);

  const [backgroundPrompt, setBackgroundPrompt] = useState("");
  const [thumbnailPrompt, setThumbnailPrompt] = useState("");
  const [promptsReady, setPromptsReady] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>("idle");

  const promptsInitialized = useRef(false);
  const lastSaved = useRef({ background: "", thumbnail: "" });
  const latestPrompts = useRef({ background: "", thumbnail: "" });
  const saveSeq = useRef(0);

  useEffect(() => {
    latestPrompts.current = { background: backgroundPrompt, thumbnail: thumbnailPrompt };
  }, [backgroundPrompt, thumbnailPrompt]);

  // Flush a pending debounce when the page closes so an edit is not lost.
  useEffect(() => {
    return () => {
      if (!promptsInitialized.current) return;
      const pending = latestPrompts.current;
      if (
        pending.background === lastSaved.current.background &&
        pending.thumbnail === lastSaved.current.thumbnail
      ) {
        return;
      }
      void apiRequest({
        method: "PATCH",
        path: "/settings",
        body: {
          imageBackgroundPrompt: pending.background,
          imageThumbnailPrompt: pending.thumbnail,
        },
      }).catch(() => undefined);
    };
  }, []);

  // Prompt init: once, from settings, with the legacy `imagePrompt` fallback.
  useEffect(() => {
    if (!data || promptsInitialized.current) return;
    const prompts = normalizeImagePrompts(data.settings);
    setBackgroundPrompt(prompts.background);
    setThumbnailPrompt(prompts.thumbnail);
    lastSaved.current = prompts;
    promptsInitialized.current = true;
    setPromptsReady(true);
  }, [data]);

  // Prompt autosave: 350 ms debounce, no PATCH before the initial settings land.
  useEffect(() => {
    if (!promptsReady) return;
    if (
      backgroundPrompt === lastSaved.current.background &&
      thumbnailPrompt === lastSaved.current.thumbnail
    ) {
      return;
    }
    const sequence = ++saveSeq.current;
    setSaveState("saving");
    const timer = window.setTimeout(() => {
      void apiRequest({
        method: "PATCH",
        path: "/settings",
        body: {
          imageBackgroundPrompt: backgroundPrompt,
          imageThumbnailPrompt: thumbnailPrompt,
        },
      })
        .then(() => {
          if (sequence !== saveSeq.current) return;
          lastSaved.current = { background: backgroundPrompt, thumbnail: thumbnailPrompt };
          setSaveState("saved");
          setBanner((current) => (current?.title === SAVE_ERROR ? null : current));
        })
        .catch((error: unknown) => {
          if (sequence !== saveSeq.current) return;
          setSaveState("error");
          setBanner({ title: SAVE_ERROR, detail: errorMessage(error) });
        });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [backgroundPrompt, thumbnailPrompt, promptsReady]);

  useEffect(() => {
    if (saveState !== "saved") return;
    const timer = window.setTimeout(() => setSaveState("idle"), 1_800);
    return () => window.clearTimeout(timer);
  }, [saveState]);

  const filteredBatches = useMemo(
    () => filterBatchesByDate(data?.batches ?? [], fromDate, toDate),
    [data?.batches, fromDate, toDate],
  );
  const batchIds = useMemo(
    () => [...new Set(filteredBatches.map((batch) => batch.batch_id).filter(Boolean))],
    [filteredBatches],
  );
  const filteredJobs = useMemo(
    () => filterJobsByBatchIds(data?.imageJobs ?? [], new Set(batchIds)),
    [data?.imageJobs, batchIds],
  );
  const rows = useMemo(
    () => buildQueueRows(filteredJobs, filteredBatches, data?.profiles ?? []),
    [filteredJobs, filteredBatches, data?.profiles],
  );
  const summary = useMemo(() => summarizeQueue(rows), [rows]);

  useEffect(() => {
    if (rows.length === 0) {
      setSelectedKey(null);
      return;
    }
    if (!selectedKey || !rows.some((row) => row.key === selectedKey)) {
      setSelectedKey(rows[0].key);
    }
  }, [rows, selectedKey]);

  const selectedRow = rows.find((row) => row.key === selectedKey) ?? null;

  const previewSignature = useMemo(() => {
    if (!selectedRow) return "";
    const jobs = [...selectedRow.bgJobs, ...selectedRow.thJobs];
    return `${selectedRow.key}|${jobs.map((job) => `${job.id}:${job.updated_at}`).join(",")}`;
  }, [selectedRow]);
  const backgroundCandidates = useMemo(
    () => previewCandidates(selectedRow, "background"),
    [selectedRow],
  );
  const thumbnailCandidates = useMemo(
    () => previewCandidates(selectedRow, "thumbnail"),
    [selectedRow],
  );
  const backgroundPreview = useImagePreview(backgroundCandidates, previewSignature);
  const thumbnailPreview = useImagePreview(thumbnailCandidates, previewSignature);

  const footer = useMemo(() => splitFooterDetail(buildFooterDetail(selectedRow)), [selectedRow]);
  const initialLoading = query.isLoading && !data;
  const stale = query.isError && Boolean(data);
  const refreshing = query.isFetching && !initialLoading;
  const totalJobs = data?.imageJobs.length ?? 0;

  const reload = useCallback(() => {
    setBanner(null);
    void query.refetch();
  }, [query]);

  const retryJob = useCallback(
    async (job: ImageJobListItem) => {
      if (busyJobId) return;
      setBusyJobId(job.id);
      setBanner(null);
      try {
        const result = await apiRequest<{ updated?: number }>({
          method: "POST",
          path: "/image-jobs/retry",
          body: { job_ids: [job.id], force: false },
        });
        const updated = Number(result?.updated ?? 0);
        if (updated > 0) {
          setStatusLabel("Retry queued.");
          toast("Retry queued.", "success");
        } else {
          setStatusLabel("No image jobs to reset.");
          toast("No image jobs to reset.", "warning");
        }
        await query.refetch();
      } catch (error) {
        setStatusLabel("Unable to retry job.");
        setBanner({ title: "Unable to retry job.", detail: errorMessage(error) });
        toast("Unable to retry job.", "danger");
      } finally {
        setBusyJobId(null);
      }
    },
    [busyJobId, query],
  );

  const openJob = useCallback(async (job: ImageJobListItem) => {
    const path = job.output_image_path;
    if (!path) {
      setBanner({ title: "This job has no output file yet." });
      return;
    }
    const result = await window.camxora.files.open(path);
    if (!result.ok) {
      setBanner({
        title: "Unable to open the output file.",
        detail: result.error.message || "The file may have been moved or deleted.",
      });
    }
  }, []);

  const clearQueue = useCallback(async () => {
    if (batchIds.length === 0 || clearing) return;
    setClearing(true);
    setBanner(null);
    let deleted = 0;
    try {
      for (const batchId of batchIds) {
        const result = await apiRequest<{ deleted?: number }>({
          method: "POST",
          path: "/image-jobs/clear",
          body: { batch_id: batchId },
        });
        deleted += Number(result?.deleted ?? 0);
      }
      setStatusLabel("Queue cleared for the selected date range.");
      setClearOpen(false);
      toast(`Queue cleared for the selected date range · ${formatCount(deleted)} deleted`, "success");
      await query.refetch();
    } catch (error) {
      setStatusLabel("Unable to clear queue.");
      setBanner({ title: "Unable to clear queue.", detail: errorMessage(error) });
      toast("Unable to clear queue.", "danger");
    } finally {
      setClearing(false);
    }
  }, [batchIds, clearing, query]);

  return (
    <div className="pb-6" data-testid="image-workspace">
      <PageHeader
        eyebrow="Workspace"
        title="Image"
        description="Review background and thumbnail jobs, preview outputs and manage the prompts."
        actions={stale ? <Badge tone="warning">Stale</Badge> : undefined}
      />

      <div className="space-y-4 p-6">
        {query.isError ? (
          <Card className="border-danger/30 bg-danger-soft px-4 py-3" role="alert">
            <p className="text-body font-medium text-danger">{LOAD_ERROR}</p>
            <p className="mt-1 text-meta text-text-secondary">
              {query.isError && !data
                ? errorMessage(query.error)
                : "The last loaded rows are still shown. Check your connection and retry."}
            </p>
            <Button className="mt-3" variant="secondary" onClick={reload}>
              Retry
            </Button>
          </Card>
        ) : null}

        {banner ? (
          <Card className="border-danger/30 bg-danger-soft px-4 py-3" role="alert">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-body font-medium text-danger">{banner.title}</p>
                {banner.detail ? (
                  <p className="mt-1 text-meta text-text-secondary">{banner.detail}</p>
                ) : null}
              </div>
              <Button variant="ghost" onClick={() => setBanner(null)}>
                Dismiss
              </Button>
            </div>
          </Card>
        ) : null}

        {data?.batchesUnavailable ? (
          <p className="text-meta text-warning">
            Batch metadata is unavailable. Dates fall back to each job's creation date.
          </p>
        ) : null}
        {data?.settingsUnavailable ? (
          <p className="text-meta text-warning">
            Prompts could not be loaded. You can still edit them; saving will retry.
          </p>
        ) : null}

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-caption text-text-muted">From</span>
            <input
              type="date"
              value={fromDate}
              max={toDate || undefined}
              onChange={(event) => setFromDate(event.target.value)}
              className="h-8 rounded-control border border-border bg-surface-1 px-2 text-body text-text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-caption text-text-muted">To</span>
            <input
              type="date"
              value={toDate}
              min={fromDate || undefined}
              onChange={(event) => setToDate(event.target.value)}
              className="h-8 rounded-control border border-border bg-surface-1 px-2 text-body text-text-primary focus:border-accent focus:outline-none"
            />
          </label>
          <Button variant="secondary" onClick={reload} disabled={query.isFetching}>
            {query.isFetching ? "Reloading…" : "Reload"}
          </Button>
          <div className="ml-auto flex items-center gap-3">
            {refreshing ? <StatusDot tone="accent" label="Refreshing…" /> : null}
            <span className="text-caption text-text-muted">
              {formatCount(totalJobs)} jobs loaded
            </span>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Card className="px-4 py-3">
            <p className="text-caption text-text-muted">Date Range</p>
            <p className="mt-1 font-mono text-title text-text-primary" data-testid="image-stat-range">
              {fromDate || "—"} → {toDate || "—"}
            </p>
          </Card>
          <Card className="px-4 py-3">
            <p className="text-caption text-text-muted">Matched Batches</p>
            <p className="mt-1 text-title font-semibold text-text-primary" data-testid="image-stat-batches">
              {initialLoading ? "--" : formatCount(filteredBatches.length)}
            </p>
          </Card>
          <Card className="px-4 py-3">
            <p className="text-caption text-text-muted">Queue Status</p>
            <p className="mt-1 truncate text-title font-semibold text-text-primary" data-testid="image-stat-status" title={statusLabel}>
              {initialLoading ? "--" : statusLabel}
            </p>
          </Card>
        </div>

        {initialLoading ? (
          <Card className="p-6 text-body text-text-secondary">Loading image workspace...</Card>
        ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
            <div className="min-w-0 space-y-4">
              <Card className="overflow-hidden">
                <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
                  <h2 className="text-title font-semibold text-text-primary">Job Queue</h2>
                  <p className="text-meta text-text-muted" data-testid="image-summary">
                    {summary.text}
                  </p>
                </div>

                <Table className="table-fixed">
                  <THead className="sticky top-0 z-10">
                    <TR className="hover:bg-surface-2">
                      <TH className="w-[120px]">Date</TH>
                      <TH className="w-[150px]">Channel</TH>
                      <TH className="w-[90px]">Role</TH>
                      <TH className="w-[96px]">BG</TH>
                      <TH className="w-[96px]">TH</TH>
                      <TH className="w-[150px]">BG File</TH>
                      <TH className="w-[150px]">TH File</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {rows.length === 0 ? (
                      <TR className="hover:bg-transparent">
                        <TD colSpan={7} className="h-14 text-center text-text-muted">
                          {emptyQueueMessage(totalJobs, filteredBatches.length, filteredJobs.length)}
                        </TD>
                      </TR>
                    ) : (
                      rows.map((row) => {
                        const selected = row.key === selectedKey;
                        return (
                          <TR
                            key={row.key}
                            data-testid={`image-row-${row.key}`}
                            aria-selected={selected}
                            tabIndex={0}
                            onClick={() => setSelectedKey(row.key)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                setSelectedKey(row.key);
                              }
                            }}
                            className={`cursor-pointer ${
                              selected ? "bg-accent-soft hover:bg-accent-soft" : ""
                            }`}
                          >
                            <TD
                              className={`h-8 border-l-2 ${
                                selected ? "border-accent" : "border-transparent"
                              } truncate font-mono text-meta`}
                              title={row.albumLabel}
                            >
                              {row.dateLabel}
                            </TD>
                            <TD className="h-8 truncate" title={row.albumLabel}>
                              {row.profileName}
                            </TD>
                            <TD className="h-8 truncate">{row.role || "—"}</TD>
                            <TD className="h-8">
                              <StatusChip
                                job={row.bgJob}
                                onRetry={retryJob}
                                onOpen={openJob}
                                busy={busyJobId === row.bgJob?.id}
                              />
                            </TD>
                            <TD className="h-8">
                              <StatusChip
                                job={row.thJob}
                                onRetry={retryJob}
                                onOpen={openJob}
                                busy={busyJobId === row.thJob?.id}
                              />
                            </TD>
                            <TD
                              className="h-8 truncate text-meta text-text-secondary"
                              data-testid="image-bg-file"
                              title={row.bgJob?.output_image_path ?? ""}
                            >
                              {basenameOrDash(row.bgJob?.output_image_path)}
                            </TD>
                            <TD
                              className="h-8 truncate text-meta text-text-secondary"
                              data-testid="image-th-file"
                              title={row.thJob?.output_image_path ?? ""}
                            >
                              {basenameOrDash(row.thJob?.output_image_path)}
                            </TD>
                          </TR>
                        );
                      })
                    )}
                  </TBody>
                </Table>

                <div className="space-y-1 border-t border-border px-4 py-3">
                  <p className="text-meta text-text-primary">
                    {selectedRow ? selectedRow.albumLabel : "No album selected"}
                  </p>
                  <p className="text-caption text-text-muted">
                    {selectedRow
                      ? `${selectedRow.dateLabel} · ${selectedRow.profileName} (${
                          selectedRow.role || "—"
                        })`
                      : "Select a queue row to preview background and thumbnail."}
                  </p>
                  {footer.info ? (
                    <p className="text-caption text-text-secondary" data-testid="image-detail">
                      {footer.info}
                    </p>
                  ) : null}
                  {footer.errors ? (
                    <p className="text-caption text-danger" data-testid="image-detail-error">
                      {footer.errors}
                    </p>
                  ) : null}
                </div>
              </Card>

              <Card className="p-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-title font-semibold text-text-primary">Prompts</h2>
                  <div className="flex items-center gap-2">
                    {saveState === "saved" ? (
                      <span className="text-caption text-success" data-testid="image-save-state">
                        Saved
                      </span>
                    ) : null}
                    {saveState === "saving" ? (
                      <span className="text-caption text-text-muted" data-testid="image-save-state">
                        Saving…
                      </span>
                    ) : null}
                    {saveState === "error" ? (
                      <span className="text-caption text-danger" data-testid="image-save-state">
                        Not saved
                      </span>
                    ) : null}
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setBackgroundPrompt(lastSaved.current.background);
                        setThumbnailPrompt(lastSaved.current.thumbnail);
                        setSaveState("idle");
                      }}
                      disabled={!promptsReady}
                    >
                      Reset
                    </Button>
                  </div>
                </div>
                <div className="mt-3 grid gap-4 xl:grid-cols-2">
                  <label className="flex flex-col gap-1">
                    <span className="text-caption text-text-muted">Background prompt</span>
                    <textarea
                      value={backgroundPrompt}
                      onChange={(event) => setBackgroundPrompt(event.target.value)}
                      rows={5}
                      maxLength={20_000}
                      disabled={!promptsReady}
                      data-testid="image-prompt-background"
                      className="w-full resize-y rounded-control border border-border bg-surface-1 px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none disabled:opacity-40"
                      placeholder="Describe the background for album art"
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-caption text-text-muted">Thumbnail prompt</span>
                    <textarea
                      value={thumbnailPrompt}
                      onChange={(event) => setThumbnailPrompt(event.target.value)}
                      rows={5}
                      maxLength={20_000}
                      disabled={!promptsReady}
                      data-testid="image-prompt-thumbnail"
                      className="w-full resize-y rounded-control border border-border bg-surface-1 px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none disabled:opacity-40"
                      placeholder="Describe the thumbnail treatment"
                    />
                  </label>
                </div>
                <div className="mt-3 flex items-center justify-between gap-3 border-t border-border pt-3">
                  <p className="text-caption text-text-muted">
                    Clear removes queue records only. Generated files on disk are not deleted.
                  </p>
                  <Button
                    variant="danger"
                    data-testid="image-clear"
                    disabled={batchIds.length === 0 || clearing}
                    onClick={() => setClearOpen(true)}
                  >
                    Clear Queue
                  </Button>
                </div>
              </Card>
            </div>

            <div className="space-y-4">
              <ImagePreviewCard
                title="Background Preview"
                subtitle={basenameOrDash(selectedRow?.bgJob?.output_image_path)}
                state={backgroundPreview}
                hasSelection={Boolean(selectedRow)}
                testId="image-preview-background"
              />
              <ImagePreviewCard
                title="Thumbnail Preview"
                subtitle={basenameOrDash(selectedRow?.thJob?.output_image_path)}
                state={thumbnailPreview}
                hasSelection={Boolean(selectedRow)}
                testId="image-preview-thumbnail"
              />
            </div>
          </div>
        )}
      </div>

      <Dialog open={clearOpen} onOpenChange={setClearOpen}>
        <DialogContent
          title="Clear queue?"
          description={`This removes every image job for ${fromDate || "the start of the range"} – ${
            toDate || "today"
          }. Generated files on disk are not deleted.`}
        >
          <p className="text-body text-text-secondary">
            {formatCount(batchIds.length)} batch{batchIds.length === 1 ? "" : "es"} will be cleared.
            This cannot be undone.
          </p>
          <div className="mt-5 flex justify-end gap-2">
            <DialogClose asChild>
              <Button variant="secondary">Cancel</Button>
            </DialogClose>
            <Button
              variant="danger"
              loading={clearing}
              onClick={() => void clearQueue()}
              data-testid="image-clear-confirm"
            >
              Clear queue
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
