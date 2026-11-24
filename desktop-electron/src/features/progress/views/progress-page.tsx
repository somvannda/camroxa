import { useCallback, useMemo, useState } from "react";
import { Icon } from "../../../components/icon";
import { PageHeader } from "../../../components/page-header";
import { Card } from "../../../components/card";
import { apiRequest, errorMessage } from "../../../lib/api";
import { DownloadQueue } from "../download-queue";
import { ProgressDetail } from "../progress-detail";
import { ProgressErrorBanner } from "../progress-error-banner";
import { ProgressStatCards } from "../progress-stat-cards";
import { ProgressTable } from "../progress-table";
import { ProgressToolbar } from "../progress-toolbar";
import { copyText } from "../progress-clipboard";
import {
  DEFAULT_LIMIT,
  countStats,
  downloadQueueRows,
  filterProgressRows,
  rowKey,
  todayYmd,
  type StageFilter,
} from "../progress-format";
import type { ImageJobsRetryResponse, ImageJobsSyncManualResponse, ProgressRow } from "../progress-types";
import { useDownloadQueue } from "../use-download-queue";
import { useManualInspections } from "../use-manual-inspections";
import { useProgressFeed } from "../use-progress-feed";
import { useVideoPipeline } from "../use-video-pipeline";
import { useYoutubeUpload } from "../use-youtube-upload";
import { YoutubeUploadDialog } from "../youtube-upload-dialog";
import { YoutubeUploadPanel } from "../youtube-upload-panel";
import { isUploadCandidate, uploadControl } from "../youtube-upload-format";

interface ActionNotice {
  tone: "success" | "danger" | "warning";
  text: string;
}

function clockLabel(value: number | null): string | null {
  if (!value) return null;
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

export function ProgressPage() {
  const [from, setFrom] = useState(() => todayYmd());
  const [to, setTo] = useState(() => todayYmd());
  const [activeOnly, setActiveOnly] = useState(false);
  const [limit, setLimit] = useState<number>(DEFAULT_LIMIT);
  const [stage, setStage] = useState<StageFilter>("all");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [notice, setNotice] = useState<ActionNotice | null>(null);
  const [syncingBatch, setSyncingBatch] = useState<string | null>(null);

  const feed = useProgressFeed({ from, to, activeOnly, limit });
  const pipeline = useVideoPipeline();
  const downloadsFeed = useDownloadQueue();
  const sourceMode = feed.settings?.imageSourceMode ?? feed.settings?.image_source_mode;
  const manualMode = String(sourceMode ?? "").toLowerCase() === "manual";
  const manual = useManualInspections(manualMode, feed.rows);
  const uploads = useYoutubeUpload(feed.rows);

  const visibleRows = useMemo(
    () => filterProgressRows(feed.rows, { activeOnly, stage, limit }),
    [feed.rows, activeOnly, stage, limit],
  );
  const statsRows = useMemo(
    () => filterProgressRows(feed.rows, { activeOnly, stage, limit: null }),
    [feed.rows, activeOnly, stage],
  );
  const stats = useMemo(
    () => countStats(statsRows, manualMode, manual.waitingKeys),
    [statsRows, manualMode, manual.waitingKeys],
  );
  const downloads = useMemo(
    () => downloadQueueRows(downloadsFeed.snapshot?.items ?? [], feed.rows),
    [downloadsFeed.snapshot, feed.rows],
  );

  const selectedRow = useMemo(
    () => visibleRows.find((row) => rowKey(row) === selectedKey) ?? null,
    [visibleRows, selectedKey],
  );

  const runFolder = useCallback(
    async (path: string) => {
      if (!path) {
        setNotice({ tone: "warning", text: "This run has no folder path." });
        return;
      }
      const ensured = await window.camxora.files.ensureDir(path);
      if (!ensured.ok) {
        setNotice({ tone: "danger", text: `Unable to create the run folder. ${ensured.error.message}` });
        return;
      }
      const opened = await window.camxora.files.open(path);
      if (!opened.ok) {
        setNotice({ tone: "danger", text: `Unable to open the run folder. ${opened.error.message}` });
      }
    },
    [],
  );

  const revealPath = useCallback(async (path: string) => {
    if (!path) return;
    const result = await window.camxora.files.reveal(path);
    if (!result.ok) {
      setNotice({ tone: "danger", text: `Unable to reveal that file. ${result.error.message}` });
    }
  }, []);

  const openExternal = useCallback(async (url: string) => {
    if (!url) return;
    const result = await window.camxora.app.openExternal(url);
    if (!result.ok) {
      setNotice({ tone: "danger", text: `Unable to open that link. ${result.error.message}` });
    }
  }, []);

  const syncManual = useCallback(
    async (row: ProgressRow) => {
      const batchId = row.meta.batch_id || row.batch;
      if (!batchId) {
        setNotice({ tone: "warning", text: "This row has no batch id to sync." });
        return;
      }
      setSyncingBatch(batchId);
      setNotice(null);
      try {
        const result = await apiRequest<ImageJobsSyncManualResponse>({
          method: "POST",
          path: "/image-jobs/sync-manual",
          body: { batch_id: batchId },
        });
        setNotice({
          tone: "success",
          text: `Manual assets synced for ${batchId} (${result.updated ?? 0} updated).`,
        });
        await feed.refresh();
      } catch (error) {
        setNotice({ tone: "danger", text: errorMessage(error) });
      } finally {
        setSyncingBatch(null);
      }
    },
    [feed],
  );

  const retryImageStage = useCallback(
    async (row: ProgressRow): Promise<string> => {
      const batchId = row.meta.batch_id || row.batch;
      if (!batchId) throw new Error("This row has no batch id to retry.");
      try {
        const result = await apiRequest<ImageJobsRetryResponse>({
          method: "POST",
          path: "/image-jobs/retry",
          body: { batch_id: batchId, force: true },
        });
        await feed.refresh();
        return `Re-queued image jobs for ${batchId} (${result.updated ?? 0} updated).`;
      } catch (error) {
        throw new Error(errorMessage(error));
      }
    },
    [feed],
  );

  const retrySongs = useCallback(
    async (row: ProgressRow, kind: "draft" | "suno") => {      const batchId = row.meta.batch_id || row.batch;
      const ids =
        kind === "draft"
          ? (row.meta.draft_failed_song_ids ?? [])
          : (row.meta.suno_failed_song_ids ?? []);
      if (!batchId || ids.length === 0) return;
      try {
        for (const songId of ids) {
          await apiRequest({
            method: "POST",
            path: `/batches/${batchId}/songs/${songId}/retry-${kind}`,
          });
        }
        setNotice({
          tone: "success",
          text: `Queued ${ids.length} ${kind === "draft" ? "draft" : "Suno"} retr${
            ids.length === 1 ? "y" : "ies"
          }.`,
        });
        await feed.refresh();
      } catch (error) {
        setNotice({ tone: "danger", text: errorMessage(error) });
      }
    },
    [feed],
  );

  const recoverRow = useCallback(
    async (row: ProgressRow, mode: "missing" | "change") => {
      const batchId = row.meta.batch_id || row.batch;
      const profileId = row.meta.profile_id;
      if (!batchId || !profileId) {
        setNotice({ tone: "danger", text: "This row has no batch/profile to recover." });
        return;
      }
      let runDir: string | undefined;
      if (mode === "change") {
        const picked = await window.camxora.files.pick({
          kind: "directory",
          title: "Choose the new run folder",
        });
        if (!picked.ok || picked.data.length === 0) return;
        runDir = picked.data[0];
      }
      try {
        const result = await window.camxora.downloads.recoverRow({
          batchId,
          profileId,
          role: row.meta.role || "OK",
          mode,
          runDir,
          currentRunDir: row.meta.run_dir ?? undefined,
          expected: row.meta.expected,
        });
        if (!result.ok) {
          setNotice({ tone: "danger", text: result.error.message });
          return;
        }
        setNotice({
          tone: result.data.failed > 0 ? "danger" : "success",
          text:
            mode === "change"
              ? `Run folder changed to ${result.data.runDir}. Downloaded ${result.data.downloaded} MP3s; ${result.data.failed} failed.`
              : `Downloaded ${result.data.downloaded} missing MP3s; ${result.data.skipped} already present; ${result.data.failed} failed.`,
        });
        await feed.refresh();
      } catch (cause) {
        setNotice({
          tone: "danger",
          text: cause instanceof Error ? cause.message : "Unable to recover this run.",
        });
      }
    },
    [feed],
  );

  const deleteBatch = useCallback(
    async (row: ProgressRow) => {
      const batchId = row.meta.batch_id || row.batch;
      if (!batchId) return;
      const label = row.album?.trim() || batchId;
      if (
        !window.confirm(
          `Delete batch "${label}"?\n\nThis removes the batch and both Primary/Secondary channel rows. It cannot be undone.`,
        )
      ) {
        return;
      }
      try {
        await apiRequest({ method: "DELETE", path: `/batches/${batchId}` });
        setNotice({ tone: "success", text: `Deleted batch ${label}.` });
        await feed.refresh();
      } catch (error) {
        setNotice({ tone: "danger", text: errorMessage(error) });
      }
    },
    [feed],
  );

  const retryDownload = useCallback(
    async (key: string) => {
      const failure = await downloadsFeed.retry(key);
      setNotice(
        failure
          ? { tone: "danger", text: failure }
          : { tone: "success", text: "Download re-queued." },
      );
    },
    [downloadsFeed],
  );

  const cancelDownload = useCallback(
    async (key: string) => {
      const failure = await downloadsFeed.cancel(key);
      setNotice(
        failure
          ? { tone: "danger", text: failure }
          : { tone: "warning", text: "Download cancelled. The partial file was removed." },
      );
    },
    [downloadsFeed],
  );

  const revealDownload = useCallback(
    async (key: string) => {
      const failure = await downloadsFeed.reveal(key);
      if (failure) setNotice({ tone: "danger", text: failure });
    },
    [downloadsFeed],
  );

  const toggleDownloads = useCallback(
    async (paused: boolean) => {
      const failure = await downloadsFeed.setPaused(paused);
      setNotice(
        failure
          ? { tone: "danger", text: failure }
          : {
              tone: paused ? "warning" : "success",
              text: paused ? "Automatic downloads paused." : "Automatic downloads resumed.",
            },
      );
    },
    [downloadsFeed],
  );

  const clearFilters = useCallback(() => {    const today = todayYmd();
    setFrom(today);
    setTo(today);
    setActiveOnly(false);
    setLimit(DEFAULT_LIMIT);
    setStage("all");
  }, []);

  const stale = Boolean(feed.error) && feed.rows.length > 0;

  const youtubePanelFor = (row: ProgressRow) => {
    if (!isUploadCandidate(row)) return undefined;
    const key = rowKey(row);
    const channel = uploads.channelFor(row.meta.profile_id);
    const control = uploadControl({
      row: uploads.rowState(key),
      upload: uploads.uploadFor(key),
      channel,
      blockedByOther: Boolean(uploads.active && uploads.active.key !== key),
      lookupError: uploads.availabilityError,
    });
    return (
      <YoutubeUploadPanel
        channel={channel}
        control={control}
        upload={uploads.uploadFor(key)}
        preparing={uploads.preparing}
        actionError={uploads.actionError}
        onUpload={() => {
          void uploads.openConfirm(row);
        }}
        onUploadWithPlaylist={() => {
          void uploads.openConfirm(row, { pickPlaylist: true });
        }}
        onCancel={() => {
          void uploads.cancelUpload();
        }}
        onRetry={() => {
          void uploads.openConfirm(row, { retry: true });
        }}
        onOpenExternal={(url) => {
          void openExternal(url);
        }}
      />
    );
  };

  return (
    <div className="pb-6">
      <PageHeader
        eyebrow="Workspace"
        title="Progress"
        description="Operational scan of active runs, failures and recovery actions."
      />

      <div className="space-y-3 p-5">
        <ProgressToolbar
          from={from}
          to={to}
          activeOnly={activeOnly}
          limit={limit}
          stage={stage}
          busy={feed.busy}
          rangeMessage={feed.rangeMessage}
          lastLoadedAt={feed.lastLoadedAt}
          onFromChange={setFrom}
          onToChange={setTo}
          onActiveOnlyChange={setActiveOnly}
          onLimitChange={setLimit}
          onStageChange={setStage}
          onRefresh={() => {
            void feed.refresh();
          }}
        />

        {manualMode ? (
          <div
            className="flex items-start gap-3 rounded-card border border-border bg-surface-1 px-4 py-3"
            data-testid="progress-manual-notice"
          >
            <Icon name="fa-circle-info" size={16} className="mt-0.5 shrink-0 text-text-muted" />
            <p className="text-body text-text-secondary">
              Manual image mode is active. This page is the recovery handoff for missing
              background-16x9, background-9x16, thumbnail-16x9 and thumbnail-9x16 assets before
              video work continues.
            </p>
          </div>
        ) : null}

        {feed.settingsError && !manualMode ? (
          <p className="text-meta text-warning" role="status">
            Image source mode is unavailable. Manual recovery stays hidden until settings load.
          </p>
        ) : null}

        <ProgressStatCards stats={stats} loading={feed.loading && !feed.data} />

        <div className="grid items-start gap-4 min-[1600px]:grid-cols-[minmax(0,1fr)_300px]">
          <div className="min-w-0 space-y-3">
            {feed.error ? (
              <ProgressErrorBanner
                stale={stale}
                lastLoadedLabel={clockLabel(feed.lastLoadedAt)}
                onRetry={() => {
                  void feed.refresh();
                }}
              />
            ) : null}

            {notice ? (
              <Card
                className={
                  notice.tone === "danger"
                    ? "border-danger/30 bg-danger-soft px-4 py-2 text-body text-danger"
                    : notice.tone === "success"
                      ? "border-success/30 bg-success-soft px-4 py-2 text-body text-success"
                      : "border-warning/30 bg-warning-soft px-4 py-2 text-body text-warning"
                }
                role="status"
              >
                {notice.text}
              </Card>
            ) : null}

            <ProgressTable
              rows={visibleRows}
              loading={feed.loading}
              selectedKey={selectedRow ? selectedKey : null}
              manualMode={manualMode}
              onSelect={(row) => setSelectedKey(rowKey(row) === selectedKey ? null : rowKey(row))}
              onOpenExternal={(url) => {
                void openExternal(url);
              }}
              onClearFilters={clearFilters}
              pipeline={pipeline.snapshot}
              onOpenFolder={(path) => {
                void runFolder(path);
              }}
              onReveal={(path) => {
                void revealPath(path);
              }}
              onCopy={(text) => {
                void copyText(text).then((copied) => {
                  if (!copied) {
                    setNotice({ tone: "danger", text: "Unable to copy to the clipboard." });
                  }
                });
              }}
              onRetryImage={(row) => {
                void retryImageStage(row).catch((cause: unknown) => {
                  setNotice({
                    tone: "danger",
                    text: cause instanceof Error ? cause.message : "Unable to retry images.",
                  });
                });
              }}
              onPipelineCancel={() => {
                void pipeline.cancel();
              }}
              onPipelineStart={() => {
                void pipeline.start();
              }}
              onPipelineForce={(request) => {
                void pipeline.force(request);
              }}
              onPipelineRetry={(batchId) => {
                void pipeline.retry(batchId);
              }}
              onRetryDrafts={(row) => {
                void retrySongs(row, "draft");
              }}
              onRetrySuno={(row) => {
                void retrySongs(row, "suno");
              }}
              onDownloadMissing={(row) => {
                void recoverRow(row, "missing");
              }}
              onChangeRunFolder={(row) => {
                void recoverRow(row, "change");
              }}
              onUpload={(row) => {
                void uploads.openConfirm(row);
              }}
              onDeleteBatch={(row) => {
                void deleteBatch(row);
              }}
              manualFolderFor={(row) => {
                const inspection = manual.inspections[rowKey(row)];
                return inspection?.runDir ?? null;
              }}
            />
          </div>

          <div className="space-y-3 min-[1600px]:sticky min-[1600px]:top-3">
            {selectedRow ? (
              <ProgressDetail
                key={rowKey(selectedRow)}
                row={selectedRow}
                manualMode={manualMode}
                inspection={manual.inspections[rowKey(selectedRow)]}
                inspecting={Boolean(manual.inspecting[rowKey(selectedRow)])}
                syncing={syncingBatch === (selectedRow.meta.batch_id || selectedRow.batch)}
                onClose={() => setSelectedKey(null)}
                onInspect={(row) => {
                  void manual.inspectRow(row);
                }}
                onOpenFolder={(path) => {
                  void runFolder(path);
                }}
                onReveal={(path) => {
                  void revealPath(path);
                }}
                onOpenExternal={(url) => {
                  void openExternal(url);
                }}
                onSyncManual={(row) => {
                  void syncManual(row);
                }}
                onRetryImage={retryImageStage}
                youtubePanel={youtubePanelFor(selectedRow)}
              />
            ) : (
              <Card className="p-4" data-testid="progress-detail-empty">
                <p className="text-body font-medium text-text-primary">Select a run</p>
                <p className="mt-1 text-meta text-text-secondary">
                  Pick a row to see its stages, paths and recovery actions here.
                </p>
              </Card>
            )}
          </div>
        </div>

        <YoutubeUploadDialog
          confirmation={uploads.confirmation}
          channel={uploads.channelFor(uploads.confirmation?.plan.profileId)}
          starting={uploads.starting}
          error={uploads.actionError}
          onPlaylistChange={uploads.setPlaylist}
          onCancel={uploads.closeConfirm}
          onConfirm={() => {
            void uploads.confirmUpload();
          }}
        />

        <DownloadQueue
          rows={downloads}
          error={downloadsFeed.error}
          paused={downloadsFeed.snapshot?.paused ?? false}
          active={downloadsFeed.snapshot?.active ?? 0}
          concurrency={downloadsFeed.snapshot?.concurrency ?? 2}
          root={downloadsFeed.snapshot?.root ?? null}
          busy={downloadsFeed.busy}
          onRetry={(key) => {
            void retryDownload(key);
          }}
          onCancel={(key) => {
            void cancelDownload(key);
          }}
          onReveal={(key) => {
            void revealDownload(key);
          }}
          onOpenFolder={(path) => {
            void runFolder(path);
          }}
          onTogglePause={(paused) => {
            void toggleDownloads(paused);
          }}
        />

      </div>
    </div>
  );
}
