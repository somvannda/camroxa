import { Icon } from "../../components/icon";
import { Button } from "../../components/button";
import { Badge } from "../../components/status";
import { classNames } from "../../lib/format";
import type { YoutubeChannelSummary, YoutubeUploadState } from "../../../electron/shared/types";
import {
  AUTO_UPLOAD_NOTE,
  formatUploadBytes,
  formatUploadProgress,
  uploadPhaseLabel,
  uploadTone,
  type UploadControl,
} from "./youtube-upload-format";

interface YoutubeUploadPanelProps {
  channel: YoutubeChannelSummary | null;
  control: UploadControl;
  upload: YoutubeUploadState | undefined;
  preparing: boolean;
  actionError: string | null;
  onUpload: () => void;
  onUploadWithPlaylist: () => void;
  onCancel: () => void;
  onRetry: () => void;
  onOpenExternal: (url: string) => void;
}

/**
 * PG-20/PG-50: the manual upload surface for one Progress row. Every disabled
 * state names its reason; there is no control that does nothing.
 */
export function YoutubeUploadPanel({
  channel,
  control,
  upload,
  preparing,
  actionError,
  onUpload,
  onUploadWithPlaylist,
  onCancel,
  onRetry,
  onOpenExternal,
}: YoutubeUploadPanelProps) {
  const uploading = control.uploading;
  const percent = upload?.percent ?? 0;
  const hasPlaylist = Boolean(control.playlistId) || (channel?.playlists.length ?? 0) > 0;

  return (
    <div
      className="mt-4 rounded-control border border-border bg-surface-2 p-3"
      data-testid="progress-upload-panel"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-card font-semibold text-text-primary">YouTube upload</h3>
          <p className="mt-0.5 text-meta text-text-secondary">
            {channel?.connected
              ? `Connected as ${channel.channelTitle || channel.profileName || "this channel"}`
              : "YouTube is not connected for this channel."}
          </p>
        </div>
        <Badge tone={uploadTone(upload)}>{uploadPhaseLabel(upload)}</Badge>
      </div>

      {upload && (uploading || upload.phase === "done") ? (
        <div className="mt-3" data-testid="progress-upload-progress">
          <div
            className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            aria-label="YouTube upload progress"
          >
            <div
              className={classNames("h-full rounded-full", upload.phase === "done" ? "bg-success" : "bg-accent")}
              style={{ width: `${Math.max(2, percent)}%` }}
            />
          </div>
          <p className="mt-1.5 text-meta text-text-secondary">
            {upload.phase === "done" ? "Upload complete" : formatUploadProgress(upload)}
          </p>
        </div>
      ) : null}

      {upload?.message ? (
        <p
          className={classNames(
            "mt-2 text-meta",
            upload.phase === "failed" || upload.phase === "cancelled" ? "text-danger" : "text-text-secondary",
          )}
          role="status"
          data-testid="progress-upload-message"
        >
          {upload.message}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {upload?.phase === "done" && upload.videoUrl ? (
          <Button
            variant="secondary"
            title={upload.videoUrl}
            data-testid="progress-upload-link"
            onClick={() => onOpenExternal(upload.videoUrl ?? "")}
          >
            <Icon name="fa-arrow-up-right-from-square" size={13} />
            Open on YouTube
          </Button>
        ) : uploading ? (
          <Button variant="secondary" onClick={onCancel} data-testid="progress-upload-cancel">
            <Icon name="fa-stop" size={13} />
            Cancel upload
          </Button>
        ) : (
          <>
            <Button
              variant="primary"
              onClick={onUpload}
              disabled={!control.canUpload || preparing}
              loading={preparing}
              title={control.reason ?? undefined}
              data-testid="progress-upload-youtube"
            >
              <Icon name="fa-video" size={14} />
              {upload?.phase === "failed" ? "Start a new upload" : "Upload to YouTube"}
            </Button>
            {hasPlaylist ? (
              <Button
                variant="secondary"
                onClick={onUploadWithPlaylist}
                disabled={!control.canUpload || preparing}
                title={control.reason ?? control.playlistLabel ?? undefined}
                data-testid="progress-upload-with-playlist"
              >
                <Icon name="fa-list" size={13} />
                With playlist…
              </Button>
            ) : null}
            {control.canRetry ? (
              <Button variant="secondary" onClick={onRetry} disabled={preparing} data-testid="progress-upload-retry">
                <Icon name="fa-rotate-right" size={13} />
                Retry upload
              </Button>
            ) : null}
          </>
        )}
      </div>

      {control.reason && !uploading && upload?.phase !== "done" ? (
        <p className="mt-2 max-w-full text-meta text-warning" data-testid="progress-upload-reason">
          {control.reason}
        </p>
      ) : null}

      {actionError ? (
        <p className="mt-2 text-meta text-danger" role="alert" data-testid="progress-upload-error">
          {actionError}
        </p>
      ) : null}

      <p className="mt-2 text-caption text-text-muted">{AUTO_UPLOAD_NOTE}</p>
    </div>
  );
}

/** Used by the table cell so the row itself can start the same confirm flow. */
export function uploadCellHint(control: UploadControl): string | null {
  if (control.canUpload) return "Upload this merged video to YouTube";
  return control.reason;
}

export function uploadMergedLabel(mergedName: string | null, mergedBytes: number | null): string {
  if (!mergedName) return "No merged file";
  return `${mergedName} · ${formatUploadBytes(mergedBytes)}`;
}
