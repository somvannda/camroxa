import { Icon } from "../../components/icon";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Badge } from "../../components/status";
import { TBody, TD, TH, THead, TR } from "../../components/table";
import { classNames } from "../../lib/format";
import {
  P7_COPY,
  channelCellText,
  imageCellText,
  localVideoState,
  musicCellText,
  notesText,
  rowKey,
  runDateLabel,
  stageBadgeTone,
  stageLabel,
  statusBadgeTone,
  statusLabel,
  updatedCellText,
  youtubeCellText,
} from "./progress-format";
import type { ProgressRow } from "./progress-types";
import type { YoutubeUploadRowState } from "../../../electron/shared/types";

const COLUMNS = [
  "Batch",
  "Run date",
  "Channel",
  "Status",
  "Music",
  "Image",
  "Converter",
  "Merge",
  "YouTube",
  "Stage",
  "Notes",
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
  /** Main-process upload verdict per row key. */
  uploadState?: (key: string) => YoutubeUploadRowState | undefined;
  /** Starts the confirmation dialog for that row's manual upload. */
  onUpload?: (row: ProgressRow) => void;
  uploadingKey?: string | null;
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

export function ProgressTable({
  rows,
  loading,
  selectedKey,
  manualMode,
  onSelect,
  onOpenExternal,
  onClearFilters,
  uploadState,
  onUpload,
  uploadingKey,
}: ProgressTableProps) {
  const hasUnreportedVideo = rows.some((row) => localVideoState(row).source === "none");
  return (
    <Card className="overflow-hidden" data-testid="progress-table-card">
      <div className="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-title font-semibold text-text-primary">Operational rows</h2>
          <p className="mt-0.5 text-meta text-text-secondary">
            Select a row for its stage timeline, paths and recovery actions.
          </p>
        </div>
        <span className="font-mono text-caption text-text-muted">
          {loading ? "Loading" : `${rows.length} visible`}
        </span>
      </div>

      <div className="max-h-[560px] overflow-auto">
        <table className="w-full min-w-[1100px] table-fixed border-collapse text-body">
          <colgroup>
            <col className="w-[100px]" />
            <col className="w-[76px]" />
            <col className="w-[100px]" />
            <col className="w-[104px]" />
            <col className="w-[84px]" />
            <col className="w-[124px]" />
            <col className="w-[96px]" />
            <col className="w-[96px]" />
            <col className="w-[92px]" />
            <col className="w-[74px]" />
            <col className="w-[96px]" />
            <col className="w-[74px]" />
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
              const youtube = youtubeCellText(row);
              const updated = updatedCellText(row);
              const note = notesText(row);
              const channel = channelCellText(row);
              return (
                <TR
                  key={key}
                  data-testid="progress-row"
                  data-row-key={key}
                  aria-selected={selected}
                  tabIndex={0}
                  className={classNames(
                    "cursor-pointer align-top focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent",
                    selected && "bg-accent-soft hover:bg-accent-soft",
                  )}
                  onClick={() => onSelect(row)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(row);
                    }
                  }}
                >
                  <TD className="py-2 align-top">
                    <span className="block truncate font-mono text-meta text-text-primary">
                      {row.batch || "Not reported"}
                    </span>
                    {row.album ? <SubLine>{row.album}</SubLine> : null}
                  </TD>
                  <TD className="py-2 align-top font-mono text-meta">
                    {runDateLabel(row.run_date)}
                  </TD>
                  <TD className="py-2 align-top">
                    <span className="block truncate">{channel.primary}</span>
                    {channel.secondary ? <SubLine>{channel.secondary}</SubLine> : null}
                  </TD>
                  <TD className="py-2 align-top">
                    <Badge tone={statusBadgeTone(row.status)}>{statusLabel(row.status)}</Badge>
                  </TD>
                  <TD className="py-2 align-top">
                    <span className="block truncate">{music.primary}</span>
                    {music.secondary ? <SubLine>{music.secondary}</SubLine> : null}
                  </TD>
                  <TD className="py-2 align-top">
                    <span className="block truncate">{image.primary}</span>
                    {image.secondary ? <SubLine>{image.secondary}</SubLine> : null}
                  </TD>
                  <TD className="py-2 align-top text-meta">
                    {video.converter ? (
                      <span className="block truncate">{video.converter}</span>
                    ) : (
                      <span className="block text-text-muted" title={P7_COPY}>
                        Not reported
                      </span>
                    )}
                  </TD>
                  <TD className="py-2 align-top text-meta">
                    {video.merge ? (
                      <span className="block truncate">{video.merge}</span>
                    ) : (
                      <span className="block text-text-muted" title={P7_COPY}>
                        Not reported
                      </span>
                    )}
                  </TD>
                  <TD className="py-2 align-top">
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
                    {(() => {
                      const upload = uploadState?.(key);
                      if (!upload) return null;
                      if (uploadingKey === key || upload.block === "uploading") {
                        return (
                          <span className="mt-1 flex items-center gap-1 text-caption text-accent">
                            <Icon name="fa-arrow-up-from-bracket" size={11} />
                            Uploading
                          </span>
                        );
                      }
                      if (upload.block !== "none" || !onUpload) return null;
                      return (
                        <button
                          type="button"
                          className="mt-1 flex items-center gap-1 text-caption text-accent hover:text-accent-hover hover:underline"
                          title="Upload this merged video to YouTube"
                          data-testid="progress-row-upload"
                          data-row-key={key}
                          onClick={(event) => {
                            event.stopPropagation();
                            onUpload(row);
                          }}
                        >
                          <Icon name="fa-arrow-up-from-bracket" size={11} />
                          Upload
                        </button>
                      );
                    })()}
                  </TD>
                  <TD className="py-2 align-top">
                    <Badge tone={stageBadgeTone(row.stage)}>{stageLabel(row.stage)}</Badge>
                  </TD>
                  <TD className="py-2 align-top">
                    <span
                      className={classNames("block truncate", note ? "text-text-secondary" : "text-text-muted")}
                      title={note ?? undefined}
                    >
                      {note ?? "—"}
                    </span>
                  </TD>
                  <TD className="py-2 align-top font-mono text-meta">
                    <span title={updated.title ?? undefined}>{updated.primary}</span>
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </table>
      </div>

      {!loading && rows.length > 0 && hasUnreportedVideo ? (
        <p className="border-t border-border px-4 py-2 text-caption text-text-muted">{P7_COPY}.</p>
      ) : null}
    </Card>
  );
}
