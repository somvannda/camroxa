import { useCallback, useMemo, useState } from "react";
import { Info } from "lucide-react";
import { PageHeader } from "../../../components/page-header";
import { Card } from "../../../components/card";
import { apiRequest, errorMessage } from "../../../lib/api";
import { DownloadQueue } from "../download-queue";
import { ProgressDetail } from "../progress-detail";
import { ProgressErrorBanner } from "../progress-error-banner";
import { ProgressStatCards } from "../progress-stat-cards";
import { ProgressTable } from "../progress-table";
import { ProgressToolbar } from "../progress-toolbar";
import {
  DEFAULT_LIMIT,
  countStats,
  downloadQueueRows,
  filterProgressRows,
  metaLine,
  rowKey,
  summaryText,
  todayYmd,
  type StageFilter,
} from "../progress-format";
import type { ImageJobsRetryResponse, ImageJobsSyncManualResponse, ProgressRow } from "../progress-types";
import { useManualInspections } from "../use-manual-inspections";
import { useProgressFeed } from "../use-progress-feed";

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
  const sourceMode = feed.settings?.imageSourceMode ?? feed.settings?.image_source_mode;
  const manualMode = String(sourceMode ?? "").toLowerCase() === "manual";
  const manual = useManualInspections(manualMode, feed.rows);

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
    () => downloadQueueRows(feed.downloads, feed.rows),
    [feed.downloads, feed.rows],
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

  const clearFilters = useCallback(() => {
    const today = todayYmd();
    setFrom(today);
    setTo(today);
    setActiveOnly(false);
    setLimit(DEFAULT_LIMIT);
    setStage("all");
  }, []);

  const stale = Boolean(feed.error) && feed.rows.length > 0;
  const pendingDownloads = feed.downloadsLoaded ? downloads.length : null;

  return (
    <div className="pb-6">
      <PageHeader
        eyebrow="Workspace"
        title="Progress"
        description="Operational scan of active runs, failures and recovery actions."
      />

      <div className="space-y-4 p-6">
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

        <div className="space-y-2">
          <p className="text-meta text-text-secondary">
            Rows combine the API stage with the local converter and merge output available on this
            device. Missing pipeline stages are named, not guessed.
          </p>
          <p className="text-meta text-text-secondary" data-testid="progress-summary">
            {feed.error && !feed.data
              ? "Progress rows are unavailable."
              : summaryText(feed.data, feed.rows)}
          </p>
        </div>

        {manualMode ? (
          <div
            className="flex items-start gap-3 rounded-card border border-border bg-surface-1 px-4 py-3"
            data-testid="progress-manual-notice"
          >
            <Info size={16} className="mt-0.5 shrink-0 text-text-muted" aria-hidden="true" />
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

        <p className="text-caption text-text-muted" data-testid="progress-meta">
          {metaLine(visibleRows.length, feed.rows.length, pendingDownloads, stage, limit)}
        </p>

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
        />

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
          />
        ) : null}

        <DownloadQueue
          rows={downloads}
          error={feed.downloadsError}
          onReveal={(path) => {
            void revealPath(path);
          }}
          onOpenFolder={(path) => {
            void runFolder(path);
          }}
        />
      </div>
    </div>
  );
}
