import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Upload } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  usePublishDesktopInstaller,
  usePublishSoftwareUpdate,
  useUpdateSoftwareUpdateConfig,
  useUploadDesktopSoftwareUpdate,
  type DesktopInstallerFile,
} from '@/hooks/use-desktop-notifications';
import { toast } from '@/hooks/use-toast';

function extractVersionFromFilename(filename: string) {
  const match = /^Camxora-(\d+(?:\.\d+){0,2})\./i.exec(filename);
  return match?.[1] ?? null;
}

export type ReleaseEditorInitialValues = {
  version?: string;
  downloadUrl?: string;
  forceUpdate?: boolean;
  releaseNotes?: string;
};

export type ReleaseEditorMode = 'new' | 'edit-draft' | 'from-installer';

interface ReleaseEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: ReleaseEditorMode;
  initialValues?: ReleaseEditorInitialValues;
  prefilledInstaller?: DesktopInstallerFile | null;
  /** When true, dialog title emphasizes publishing the prefilled installer */
  publishIntent?: boolean;
}

const DEFAULT_PUBLISH_OPTIONS = {
  createChangelogOnPublish: true,
  notifyDesktopUsers: true,
};

export function ReleaseEditorDialog({
  open,
  onOpenChange,
  mode,
  initialValues,
  prefilledInstaller,
  publishIntent = false,
}: ReleaseEditorDialogProps) {
  const updateSoftwareUpdate = useUpdateSoftwareUpdateConfig();
  const publishSoftwareUpdate = usePublishSoftwareUpdate();
  const publishInstaller = usePublishDesktopInstaller();
  const uploadDesktopRelease = useUploadDesktopSoftwareUpdate();
  const uploadFileRef = useRef<HTMLInputElement>(null);

  const [version, setVersion] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [forceUpdate, setForceUpdate] = useState(false);
  const [releaseNotes, setReleaseNotes] = useState('');
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);
  const [createChangelogOnPublish, setCreateChangelogOnPublish] = useState(
    DEFAULT_PUBLISH_OPTIONS.createChangelogOnPublish,
  );
  const [notifyDesktopUsers, setNotifyDesktopUsers] = useState(
    DEFAULT_PUBLISH_OPTIONS.notifyDesktopUsers,
  );

  const isBusy =
    updateSoftwareUpdate.isPending ||
    publishSoftwareUpdate.isPending ||
    publishInstaller.isPending ||
    uploadDesktopRelease.isPending;

  const resetState = useCallback(() => {
    setVersion('');
    setDownloadUrl('');
    setForceUpdate(false);
    setReleaseNotes('');
    setUploadedFilename(null);
    setCreateChangelogOnPublish(DEFAULT_PUBLISH_OPTIONS.createChangelogOnPublish);
    setNotifyDesktopUsers(DEFAULT_PUBLISH_OPTIONS.notifyDesktopUsers);
    if (uploadFileRef.current) {
      uploadFileRef.current.value = '';
    }
  }, []);

  const populateForm = useCallback(() => {
    if (prefilledInstaller) {
      setDownloadUrl(prefilledInstaller.download_url);
      const parsedVersion = extractVersionFromFilename(prefilledInstaller.filename);
      setVersion(parsedVersion ?? initialValues?.version ?? '');
    } else {
      setVersion(initialValues?.version ?? '');
      setDownloadUrl(initialValues?.downloadUrl ?? '');
    }
    setForceUpdate(initialValues?.forceUpdate ?? false);
    setReleaseNotes(initialValues?.releaseNotes ?? '');
    setUploadedFilename(null);
    setCreateChangelogOnPublish(DEFAULT_PUBLISH_OPTIONS.createChangelogOnPublish);
    setNotifyDesktopUsers(DEFAULT_PUBLISH_OPTIONS.notifyDesktopUsers);
    if (uploadFileRef.current) {
      uploadFileRef.current.value = '';
    }
  }, [initialValues, prefilledInstaller]);

  useEffect(() => {
    if (open) {
      populateForm();
    }
  }, [open, populateForm]);

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      resetState();
    }
    onOpenChange(nextOpen);
  }

  function buildDraftPayload() {
    if (!version.trim()) {
      toast({ title: 'Version is required', variant: 'destructive' });
      return null;
    }
    return {
      version: version.trim(),
      download_url: downloadUrl.trim(),
      mandatory: forceUpdate,
      release_notes: releaseNotes.trim(),
    };
  }

  function saveDraft(onSuccess?: () => void) {
    const payload = buildDraftPayload();
    if (!payload) return;
    updateSoftwareUpdate.mutate(payload, {
      onSuccess: () => {
        toast({ title: 'Software update draft saved' });
        onSuccess?.();
      },
    });
  }

  function publishRelease() {
    const payload = buildDraftPayload();
    if (!payload) return;

    updateSoftwareUpdate.mutate(payload, {
      onSuccess: () => {
        const publishOptions = {
          create_changelog: createChangelogOnPublish,
          notify_desktop_users: notifyDesktopUsers,
        };

        if (prefilledInstaller) {
          publishInstaller.mutate(
            {
              filename: prefilledInstaller.filename,
              body: {
                release_notes: payload.release_notes,
                mandatory: payload.mandatory,
                create_changelog: createChangelogOnPublish,
                notify_desktop_users: notifyDesktopUsers,
              },
            },
            {
              onSuccess: (result) => {
                toast({
                  title: `Published ${result.version}`,
                  description: result.changelog_slug
                    ? `Live on /download. Changelog: ${result.changelog_slug}`
                    : `Live on /download. Notified ${result.recipients} desktop user(s).`,
                });
                handleOpenChange(false);
              },
              onError: (error: Error) =>
                toast({
                  title: 'Publish failed',
                  description: error.message,
                  variant: 'destructive',
                }),
            },
          );
          return;
        }

        publishSoftwareUpdate.mutate(publishOptions, {
          onSuccess: (result) => {
            toast({
              title: `Update ${result.version} published`,
              description: result.changelog_slug
                ? `Live on /download. Changelog post created. Notified ${result.recipients} user(s).`
                : `Live on /download. Notified ${result.recipients} active user(s).`,
            });
            handleOpenChange(false);
          },
          onError: (error: Error) =>
            toast({
              title: 'Unable to publish update',
              description: error.message,
              variant: 'destructive',
            }),
        });
      },
    });
  }

  function uploadInstaller() {
    const file = uploadFileRef.current?.files?.[0];
    if (!file) {
      toast({ title: 'Choose an installer file first', variant: 'destructive' });
      return;
    }
    uploadDesktopRelease.mutate(
      { file, version: version.trim() || undefined },
      {
        onSuccess: (result) => {
          setDownloadUrl(result.download_url);
          setUploadedFilename(result.filename);
          const parsedVersion = extractVersionFromFilename(result.filename);
          if (parsedVersion && !version.trim()) {
            setVersion(parsedVersion);
          }
          toast({
            title: 'Installer uploaded',
            description: result.draft_saved
              ? `${result.filename} saved. Download URL applied to draft.`
              : `${result.filename} (${Math.round(result.size_bytes / (1024 * 1024))} MB)`,
          });
          if (uploadFileRef.current) {
            uploadFileRef.current.value = '';
          }
        },
        onError: (error: Error) =>
          toast({
            title: 'Upload failed',
            description: error.message.includes('413')
              ? 'File too large for the server gateway (max 500 MB). If this persists after retry, contact ops — nginx may need a higher upload limit.'
              : error.message,
            variant: 'destructive',
          }),
      },
    );
  }

  const dialogTitle =
    publishIntent && prefilledInstaller
      ? `Publish ${prefilledInstaller.filename}`
      : mode === 'edit-draft'
        ? 'Edit draft release'
        : mode === 'from-installer' && prefilledInstaller
          ? `Configure ${prefilledInstaller.filename}`
          : 'New release';

  const dialogDescription =
    publishIntent && prefilledInstaller
      ? 'Review release settings, then publish to make this installer live on /download.'
      : mode === 'edit-draft'
        ? 'Update the draft release configuration. Saving does not publish publicly.'
        : 'Configure version, download URL, and release notes. Upload an installer or pick one from the table.';

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
          <DialogDescription>{dialogDescription}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="release-version">Version</Label>
            <Input
              id="release-version"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="2.5.0"
              disabled={isBusy}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="release-download-url">Download URL</Label>
            <Input
              id="release-download-url"
              value={downloadUrl}
              onChange={(e) => setDownloadUrl(e.target.value)}
              placeholder="https://downloads.camxora.com/desktop/Camxora-2.5.0.zip"
              disabled={isBusy}
            />
            <p className="text-xs text-slate-500">
              Recommended: a <span className="text-slate-400">.zip</span> of the full PyInstaller app folder
              for fully silent updates. Inno Setup <span className="text-slate-400">.exe</span> and{' '}
              <span className="text-slate-400">.msi</span> packages are also supported with quiet install flags.
            </p>
          </div>

          <div className="rounded-md border border-slate-800 bg-slate-950/40 p-3 space-y-3">
            <div>
              <p className="text-sm font-medium text-slate-200">Upload installer</p>
              <p className="mt-1 text-xs text-slate-500">
                Upload a hosted package to auto-generate an absolute download URL. Uses the version field
                above for the stored filename when provided.
              </p>
            </div>
            <Input
              ref={uploadFileRef}
              type="file"
              accept=".zip,.exe,.msi,application/zip,application/vnd.microsoft.portable-executable,application/x-msi"
              disabled={isBusy}
            />
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={uploadInstaller}
                disabled={uploadDesktopRelease.isPending || isBusy}
              >
                {uploadDesktopRelease.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="mr-2 h-4 w-4" />
                )}
                Upload installer
              </Button>
              {uploadedFilename ? (
                <p className="text-xs text-slate-400">Last upload: {uploadedFilename}</p>
              ) : null}
              {prefilledInstaller && !uploadedFilename ? (
                <p className="text-xs text-slate-400">Selected: {prefilledInstaller.filename}</p>
              ) : null}
            </div>
          </div>

          <div className="rounded-md border border-slate-800 px-3 py-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-slate-200">Force update</p>
                <p className="mt-1 text-xs text-slate-500">
                  When enabled, desktop users on an older version are blocked until they install this release.
                  They cannot dismiss the update or continue using the current app.
                </p>
              </div>
              <input
                id="release-force"
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900"
                checked={forceUpdate}
                onChange={(event) => setForceUpdate(event.target.checked)}
                disabled={isBusy}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="release-notes">Release notes</Label>
            <Textarea
              id="release-notes"
              value={releaseNotes}
              onChange={(e) => setReleaseNotes(e.target.value)}
              placeholder="Bug fixes, performance improvements, and new music workflow tools."
              rows={5}
              disabled={isBusy}
            />
          </div>

          <div className="rounded-md border border-slate-800 px-3 py-3 space-y-3">
            <p className="text-sm font-medium text-slate-200">On publish</p>
            <label className="flex items-start gap-3 text-sm text-slate-300">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900"
                checked={createChangelogOnPublish}
                onChange={(event) => setCreateChangelogOnPublish(event.target.checked)}
                disabled={isBusy}
              />
              <span>Create website changelog post (category Release notes)</span>
            </label>
            <label className="flex items-start gap-3 text-sm text-slate-300">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900"
                checked={notifyDesktopUsers}
                onChange={(event) => setNotifyDesktopUsers(event.target.checked)}
                disabled={isBusy}
              />
              <span>Notify active desktop users (in-app update prompt)</span>
            </label>
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={isBusy}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => saveDraft(() => handleOpenChange(false))}
            disabled={isBusy}
          >
            {updateSoftwareUpdate.isPending && !publishSoftwareUpdate.isPending && !publishInstaller.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            Save draft
          </Button>
          <Button type="button" onClick={publishRelease} disabled={isBusy}>
            {(publishSoftwareUpdate.isPending || publishInstaller.isPending) && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Publish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
