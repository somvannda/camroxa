import { Button } from "../../components/button";
import { Dialog, DialogContent } from "../../components/dialog";
import type { YoutubeChannelSummary } from "../../../electron/shared/types";
import { AUTO_UPLOAD_NOTE, confirmationLines, playlistChoices } from "./youtube-upload-format";
import type { UploadConfirmation } from "./use-youtube-upload";

interface YoutubeUploadDialogProps {
  confirmation: UploadConfirmation | null;
  channel: YoutubeChannelSummary | null;
  starting: boolean;
  error: string | null;
  onPlaylistChange: (playlist: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}

/**
 * Explicit confirmation before a manual upload: channel, title, visibility or
 * schedule, file and playlist. Nothing is sent until "Upload to YouTube".
 */
export function YoutubeUploadDialog({
  confirmation,
  channel,
  starting,
  error,
  onPlaylistChange,
  onCancel,
  onConfirm,
}: YoutubeUploadDialogProps) {
  const open = Boolean(confirmation);
  const plan = confirmation?.plan ?? null;
  const choices = plan ? playlistChoices(channel, plan.playlistId) : [];
  const lines = plan
    ? confirmationLines({
        channelTitle: plan.channelTitle,
        profileName: channel?.profileName ?? null,
        title: plan.title,
        visibility: plan.visibility,
        mergedName: plan.mergedName,
        mergedBytes: plan.mergedBytes,
        playlistTitle:
          choices.find((choice) => choice.value === confirmation?.playlist)?.label ??
          plan.playlistTitle,
        containsSyntheticMedia: plan.containsSyntheticMedia,
        madeForKids: plan.madeForKids,
      })
    : [];

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onCancel())}>
      <DialogContent
        title="Upload to YouTube?"
        description="This publishes the merged video to the connected channel with the profile's publication settings."
      >
        <dl className="space-y-2" data-testid="youtube-upload-confirmation">
          {lines.map((line) => (
            <div key={line.label} className="flex items-start justify-between gap-4 border-b border-border pb-2 last:border-b-0">
              <dt className="shrink-0 text-caption text-text-muted">{line.label}</dt>
              <dd className="min-w-0 break-words text-right text-meta text-text-primary">{line.value}</dd>
            </div>
          ))}
        </dl>

        {choices.length > 1 ? (
          <label className="mt-3 block">
            <span className="text-caption text-text-muted">Playlist for this upload</span>
            <select
              className="mt-1 h-8 w-full rounded-control border border-border bg-surface-1 px-2.5 text-body text-text-primary focus:border-accent focus:outline-none"
              value={confirmation?.playlist ?? "profile"}
              onChange={(event) => onPlaylistChange(event.target.value)}
              data-testid="youtube-upload-playlist"
            >
              <option value="profile">Profile default</option>
              {choices
                .filter((choice) => choice.value !== "profile")
                .map((choice) => (
                  <option key={choice.value} value={choice.value}>
                    {choice.label}
                  </option>
                ))}
            </select>
          </label>
        ) : null}

        {error ? (
          <p className="mt-3 text-meta text-danger" role="alert" data-testid="youtube-upload-confirm-error">
            {error}
          </p>
        ) : null}

        <p className="mt-3 text-caption text-text-muted">{AUTO_UPLOAD_NOTE}</p>

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel} disabled={starting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={onConfirm}
            loading={starting}
            data-testid="youtube-upload-confirm"
          >
            Upload to YouTube
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
