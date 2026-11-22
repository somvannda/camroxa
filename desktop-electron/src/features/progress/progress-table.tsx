import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../../components/icon";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Badge } from "../../components/status";
import { TBody, TD, TH, THead, TR } from "../../components/table";
import { classNames } from "../../lib/format";
import {
  PIPELINE_MISSING,
  channelCellText,
  imageCellText,
  localVideoState,
  musicCellText,
  progressPercent,
  relativeTime,
  rowKey,
  runDateLabel,
  stageBadgeTone,
  stageLabel,
  statusBadgeTone,
  updatedCellText,
  youtubeCellText,
} from "./progress-format";
import type { ProgressRow } from "./progress-types";
import type { PipelineSnapshot } from "../../../electron/shared/types";
import { localVideoForRow } from "./progress-local-video";

const COLUMNS = [
  "Run Date",
  "Channel",
  "Album",
  "Stage",
  "Progress",
  "Music",
  "Image",
  "Video (Render)",
  "Merge",
  "YouTube",
  "Updated",
];

interface ProgressTableProps {
  rows: ProgressRow[];
  loading: boolean;
  selectedKey: string | null;
  manualMode: boolean;
  onSelect: (row: ProgressRow) => void;
  onOpenExternal: (url: string) => void;
  onClearFilters: () => void;
  /** Local durable render queue, folded into the Video/Merge cells. */
  pipeline?: PipelineSnapshot | null;
  onOpenFolder?: (path: string) => void;
  onReveal?: (path: string) => void;
  onCopy?: (text: string) => void;
  onRetryImage?: (row: ProgressRow) => void;
  onRetryDrafts?: (row: ProgressRow) => void;
  onRetrySuno?: (row: ProgressRow) => void;
  onDownloadMissing?: (row: ProgressRow) => void;
  onChangeRunFolder?: (row: ProgressRow) => void;
  onUpload?: (row: ProgressRow) => void;
  onPipelineCancel?: () => void;
  onPipelineRetry?: (batchId: string) => void;
  onPipelineStart?: () => void;
  onPipelineForce?: (request: {
    mode: "force" | "repair" | "single";
    batchId?: string;
    jobIds?: string[];
  }) => void;
  manualFolderFor?: (row: ProgressRow) => string | null;
}

function SubLine({ children }: { children: string }) {
  return <p className="mt-0.5 truncate text-caption text-text-muted">{children}</p>;
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }, (_, index) => (
        <TR key={index} className="hover:bg-transparent">
          {COLUMNS.map((column) => (
            <TD key={column} className="py-2.5 align-middle">
              <div className="h-3 w-full rounded-[2px] bg-surface-3" />
            </TD>
          ))}
        </TR>
      ))}
    </>
  );
}

interface RowMenuState {
  x: number;
  y: number;
  row: ProgressRow;
}

function ContextItem({
  children,
  disabled = false,
  onClick,
  title,
}: {
  children: ReactNode;
  disabled?: boolean;
  onClick: () => void;
  title?: string;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      title={title}
      className="flex h-7 w-full items-center whitespace-nowrap rounded-[5px] px-2 text-left text-body text-text-secondary hover:bg-surface-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function ProgressTable({
  rows,
  loading,
  selectedKey,
  manualMode,
  onSelect,
  onOpenExternal,
  onClearFilters,
  pipeline,
  onOpenFolder,
  onReveal,
  onCopy,
  onRetryImage,
  onPipelineCancel,
  onPipelineRetry,
  onPipelineStart,
  onPipelineForce,
  onRetryDrafts,
  onRetrySuno,
  onDownloadMissing,
  onChangeRunFolder,
  onUpload,
  manualFolderFor,
}: ProgressTableProps) {
  const [menu, setMenu] = useState<RowMenuState | null>(null);
  const hasUnreportedVideo = rows.some((row) => localVideoState(row).source === "none");

  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(null);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("click", close);
    window.addEventListener("contextmenu", close);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("contextmenu", close);
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [menu]);

  const openMenu = (event: React.MouseEvent, row: ProgressRow) => {
    event.preventDefault();
    event.stopPropagation();
    onSelect(row);
    setMenu({
      x: Math.min(event.clientX, Math.max(8, window.innerWidth - 316)),
      y: Math.max(
        8,
        Math.min(event.clientY, window.innerHeight - Math.min(560, window.innerHeight - 16)),
      ),
      row,
    });
  };

  const run = (action: () => void) => {
    setMenu(null);
    action();
  };

  const runDir = menu?.row.meta.run_dir?.trim() ?? "";
  const youtubeUrl = menu?.row.meta.youtube_url?.trim() ?? "";
  const rowAlbum = menu?.row.album?.trim() ?? "";
  const canRetryImages = Boolean(menu && onRetryImage);
  const menuLocal = menu ? localVideoForRow(menu.row, pipeline) : null;
  const draftFailures = menu?.row.meta.draft_failed_song_ids ?? [];
  const sunoFailures = menu?.row.meta.suno_failed_song_ids ?? [];
  const manualFolder = menu && manualFolderFor ? manualFolderFor(menu.row) : null;
  const expected = menu?.row.meta.expected ?? 0;
  const saved = menu?.row.meta.saved ?? menu?.row.meta.download_ready ?? 0;
  const missingMp3s = Math.max(0, expected - saved);

  return (
    <>
    <Card className="overflow-hidden" data-testid="progress-table-card">
      <div className="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-title font-semibold text-text-primary">Operational rows</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            Select a row for its stage timeline, paths and recovery actions. Right-click a row for
            run-folder, copy and upload actions.
          </p>
        </div>
        <span className="font-mono text-caption text-text-muted">
          {loading ? "Loading" : null}
        </span>
      </div>

      <div className="max-h-[560px] overflow-auto">
        <table className="w-full min-w-[952px] table-fixed border-collapse text-body">
          <colgroup>
            <col className="w-[86px]" />
            <col className="w-[104px]" />
            <col className="w-[128px]" />
            <col className="w-[76px]" />
            <col className="w-[80px]" />
            <col className="w-[76px]" />
            <col className="w-[104px]" />
            <col className="w-[88px]" />
            <col className="w-[62px]" />
            <col className="w-[76px]" />
            <col className="w-[72px]" />
          </colgroup>
          <THead className="sticky top-0 z-10">
            <TR className="hover:bg-transparent">
              {COLUMNS.map((column) => (
                <TH key={column} className="bg-surface-2">
                  {column}
                </TH>
              ))}
            </TR>
          </THead>
          <TBody>
            {loading && rows.length === 0 ? <SkeletonRows /> : null}

            {!loading && rows.length === 0 ? (
              <TR className="hover:bg-transparent">
                <TD colSpan={COLUMNS.length} className="py-10 text-center">
                  <p className="text-body text-text-secondary">No runs match these filters.</p>
                  <Button className="mt-3" variant="secondary" onClick={onClearFilters}>
                    Clear filters
                  </Button>
                </TD>
              </TR>
            ) : null}

            {rows.map((row) => {
              const key = rowKey(row);
              const selected = key === selectedKey;
              const music = musicCellText(row);
              const image = imageCellText(row, manualMode);
              const video = localVideoState(row);
              const progress = progressPercent(row);
              const stageText = stageLabel(row.stage);
              const stageTone = stageBadgeTone(row.stage);
              const local = localVideoForRow(row, pipeline);
              const displayStage = local.failed
                ? "Error"
                : local.mergedPath
                  ? "Done"
                  : local.total > 0 && local.done === local.total
                    ? "Merge"
                    : local.running
                      ? "Render"
                      : stageText;
              const displayStageTone = local.failed
                ? "danger"
                : local.mergedPath
                  ? "success"
                  : local.running
                    ? "accent"
                    : stageTone;
              const displayProgress =
                local.total > 0
                  ? {
                      text: local.percent >= 100 ? "100%" : `${local.percent}%`,
                      percent: local.percent,
                    }
                  : progress;
              const videoPrimary = local.videoPrimary ?? video.converter;
              const videoSecondary = local.videoSecondary;
              const mergePrimary = local.mergePrimary ?? video.merge;
              const youtube = youtubeCellText(row);
              const backendUpdated = updatedCellText(row);
              const updated =
                local.updatedAt !== null
                  ? {
                      primary: relativeTime(new Date(local.updatedAt).toISOString()),
                      secondary: null,
                      title: new Date(local.updatedAt).toLocaleString(),
                    }
                  : backendUpdated;
              const channel = channelCellText(row);
              const progressTone = statusBadgeTone(row.status);
              const role =
                channel.secondary === "OK"
                  ? "Primary"
                  : channel.secondary === "ALT"
                    ? "Secondary"
                    : channel.secondary;
              return (
                <TR
                  key={key}
                  data-testid="progress-row"
                  data-row-key={key}
                  aria-selected={selected}
                  tabIndex={0}
                  className={classNames(
                    "cursor-pointer align-middle focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent",
                    selected && "bg-accent-soft hover:bg-accent-soft",
                  )}
                  onClick={() => onSelect(row)}
                  onContextMenu={(event) => openMenu(event, row)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(row);
                    }
                    if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
                      event.preventDefault();
                      const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
                      setMenu({ x: rect.left + 24, y: rect.top + 24, row });
                    }
                  }}
                >
                  <TD className="py-2 font-mono text-meta text-text-primary">
                    {runDateLabel(row.run_date)}
                    <SubLine>{row.batch || "Not reported"}</SubLine>
                  </TD>
                  <TD className="py-2">
                    <span className="block truncate text-meta text-text-primary">
                      {channel.primary}
                    </span>
                    {role ? <SubLine>{role}</SubLine> : null}
                  </TD>
                  <TD className="py-2">
                    <span className="block truncate text-meta text-text-primary" title={row.album ?? ""}>
                      {row.album?.trim() || "—"}
                    </span>
                  </TD>
                  <TD className="py-2">
                    <Badge tone={displayStageTone}>{displayStage}</Badge>
                  </TD>
                  <TD className="py-2">
                    <div className="flex items-center gap-1.5">
                      <div
                        className="h-1.5 w-12 overflow-hidden rounded-full bg-surface-3"
                        role="progressbar"
                        aria-label="Stage progress"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={displayProgress.percent}
                      >
                        <div
                          className={classNames(
                            "h-full rounded-full",
                            displayProgress.percent >= 100
                              ? "bg-success"
                              : progressTone === "danger"
                                ? "bg-danger"
                                : "bg-accent",
                          )}
                          style={{ width: `${displayProgress.percent}%` }}
                        />
                      </div>
                      <span className="text-caption text-text-secondary text-tabular">
                        {displayProgress.text}
                      </span>
                    </div>
                  </TD>
                  <TD className="py-2">
                    <span className="block truncate text-meta text-text-primary">{music.primary}</span>
                    {music.secondary ? <SubLine>{music.secondary}</SubLine> : null}
                  </TD>
                  <TD className="py-2">
                    <span className="block truncate text-meta text-text-primary">{image.primary}</span>
                    {image.secondary ? <SubLine>{image.secondary}</SubLine> : null}
                  </TD>
                  <TD className="py-2 text-meta" data-testid="progress-video">
                    {videoPrimary ? (
                      <>
                        <span className="block truncate">{videoPrimary}</span>
                        {videoSecondary ? <SubLine>{videoSecondary}</SubLine> : null}
                      </>
                    ) : (
                      <span className="block text-text-muted" title={PIPELINE_MISSING}>
                        —
                      </span>
                    )}
                  </TD>
                  <TD className="py-2 text-meta" data-testid="progress-merge">
                    {mergePrimary ? (
                      <span className="block truncate">{mergePrimary}</span>
                    ) : (
                      <span className="block text-text-muted" title={PIPELINE_MISSING}>
                        —
                      </span>
                    )}
                  </TD>
                  <TD className="py-2">
                    {youtube.url ? (
                      <button
                        type="button"
                        className="inline-flex max-w-full items-center gap-1 truncate text-meta text-accent hover:text-accent-hover hover:underline"
                        title={youtube.url}
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenExternal(youtube.url ?? "");
                        }}
                      >
                        <Icon name="fa-arrow-up-right-from-square" size={12} />
                        <span className="truncate">{youtube.primary}</span>
                      </button>
                    ) : (
                      <Badge tone={youtube.tone}>{youtube.primary}</Badge>
                    )}
                  </TD>
                  <TD className="py-2 font-mono text-caption text-text-secondary">
                    <span title={updated.title ?? undefined}>{updated.primary}</span>
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </table>
      </div>

      {!loading && rows.length > 0 && hasUnreportedVideo ? (
        <p className="border-t border-border px-4 py-2 text-caption text-text-muted">{PIPELINE_MISSING}.</p>
      ) : null}
    </Card>

    {menu
      ? createPortal(
          <div
            role="menu"
            aria-label="Progress row actions"
            className="fixed z-[100] max-h-[calc(100vh-16px)] w-[300px] overflow-y-auto rounded-card border border-border bg-surface-1 p-1 shadow-[0_18px_48px_rgba(0,0,0,.55)]"
            style={{ left: menu.x, top: menu.y }}
            onClick={(event) => event.stopPropagation()}
            data-testid="progress-row-menu"
          >
            <ContextItem
              disabled={!runDir}
              onClick={() => run(() => onOpenFolder?.(runDir))}
            >
              <Icon name="fa-folder-open" size={11} className="mr-2" />
              Open run folder
            </ContextItem>
            <ContextItem
              disabled={!runDir}
              onClick={() => run(() => onDownloadMissing?.(menu.row))}
            >
              <Icon name="fa-download" size={11} className="mr-2" />
              Download missing MP3s{missingMp3s > 0 ? ` (${missingMp3s})` : ""}
            </ContextItem>
            <ContextItem
              disabled={!runDir}
              onClick={() => run(() => onChangeRunFolder?.(menu.row))}
            >
              <Icon name="fa-folder-tree" size={11} className="mr-2" />
              Change run folder & resume…
            </ContextItem>
            <ContextItem
              disabled={!menuLocal?.mergedPath && !menuLocal?.outputPath}
              onClick={() =>
                run(() => onReveal?.(menuLocal?.mergedPath ?? menuLocal?.outputPath ?? ""))
              }
            >
              <Icon name="fa-film" size={11} className="mr-2" />
              Reveal rendered video
            </ContextItem>
            <ContextItem
              disabled={!menu.row.meta.batch_id}
              onClick={() => run(() => onCopy?.(menu.row.meta.batch_id))}
            >
              <Icon name="fa-copy" size={11} className="mr-2" />
              Copy batch ID
            </ContextItem>
            <ContextItem disabled={!rowAlbum} onClick={() => run(() => onCopy?.(rowAlbum))}>
              <Icon name="fa-copy" size={11} className="mr-2" />
              Copy album
            </ContextItem>
            {draftFailures.length > 0 ? (
              <ContextItem onClick={() => run(() => onRetryDrafts?.(menu.row))}>
                <Icon name="fa-rotate-right" size={11} className="mr-2" />
                Retry failed drafts ({draftFailures.length})
              </ContextItem>
            ) : null}
            {sunoFailures.length > 0 ? (
              <ContextItem onClick={() => run(() => onRetrySuno?.(menu.row))}>
                <Icon name="fa-rotate-right" size={11} className="mr-2" />
                Retry failed Suno ({sunoFailures.length})
              </ContextItem>
            ) : null}
            {manualFolder ? (
              <ContextItem onClick={() => run(() => onOpenFolder?.(manualFolder))}>
                <Icon name="fa-folder-open" size={11} className="mr-2" />
                Open manual folder
              </ContextItem>
            ) : null}
            <div className="my-1 h-px bg-border" />
            <ContextItem
              disabled={!canRetryImages}
              onClick={() => run(() => onRetryImage?.(menu.row))}
            >
              <Icon name="fa-rotate-right" size={11} className="mr-2" />
              Retry images
            </ContextItem>
            <ContextItem
              disabled={!menuLocal?.running || !onPipelineCancel}
              onClick={() => run(() => onPipelineCancel?.())}
            >
              <Icon name="fa-stop" size={11} className="mr-2" />
              Cancel video render
            </ContextItem>
            <ContextItem
              disabled={!onPipelineStart}
              onClick={() => run(() => onPipelineStart?.())}
            >
              <Icon name="fa-play" size={11} className="mr-2" />
              Continue video render
            </ContextItem>
            <ContextItem
              disabled={!menuLocal?.retryBatchId || !onPipelineRetry}
              onClick={() => run(() => onPipelineRetry?.(menuLocal?.retryBatchId ?? ""))}
            >
              <Icon name="fa-rotate-right" size={11} className="mr-2" />
              Retry failed render
            </ContextItem>
            <ContextItem
              disabled={!menuLocal || menuLocal.total === 0 || !onPipelineForce}
              onClick={() =>
                run(() =>
                  onPipelineForce?.({
                    mode: "force",
                    batchId: menuLocal?.jobs[0]
                      ? pipeline?.jobs.find((job) => job.id === menuLocal.jobs[0].id)?.batchId
                      : undefined,
                  }),
                )
              }
            >
              <Icon name="fa-rotate-right" size={11} className="mr-2" />
              Force regenerate MP4s
            </ContextItem>
            <ContextItem
              disabled={!menuLocal || menuLocal.total === 0 || !onPipelineForce}
              onClick={() =>
                run(() =>
                  onPipelineForce?.({
                    mode: "repair",
                    batchId: menuLocal?.jobs[0]
                      ? pipeline?.jobs.find((job) => job.id === menuLocal.jobs[0].id)?.batchId
                      : undefined,
                  }),
                )
              }
            >
              <Icon name="fa-wrench" size={11} className="mr-2" />
              Repair missing/broken MP4s
            </ContextItem>
            {menuLocal?.jobs.slice(0, 8).map((job) => (
              <ContextItem
                key={job.id}
                title={job.title}
                onClick={() => run(() => onPipelineForce?.({ mode: "single", jobIds: [job.id] }))}
              >
                <Icon name="fa-film" size={11} className="mr-2" />
                <span className="min-w-0 flex-1 truncate">
                  Regenerate {job.title || "track"}
                </span>
              </ContextItem>
            ))}
            <ContextItem
              disabled={!youtubeUrl}
              onClick={() => run(() => onOpenExternal(youtubeUrl))}
            >
              <Icon name="fa-arrow-up-right-from-square" size={11} className="mr-2" />
              Open YouTube URL
            </ContextItem>
            <ContextItem disabled={!onUpload} onClick={() => run(() => onUpload?.(menu.row))}>
              <Icon name="fa-arrow-up-from-bracket" size={11} className="mr-2" />
              Upload to YouTube…
            </ContextItem>
          </div>,
          document.body,
        )
      : null}
    </>
  );
}
