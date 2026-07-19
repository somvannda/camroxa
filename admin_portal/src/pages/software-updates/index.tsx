import { useEffect, useRef, useState } from 'react';
import { Download, Loader2, Upload } from 'lucide-react';

import { InstallerFilesTable } from '@/components/software-updates/installer-files-table';
import {
  usePublishSoftwareUpdate,
  useSoftwareUpdateConfig,
  useUpdateSoftwareUpdateConfig,
  useUploadDesktopSoftwareUpdate,
  type DesktopInstallerFile,
} from '@/hooks/use-desktop-notifications';
import { toast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

function formatTimestamp(value: string | null | undefined) {
  if (!value) return 'Not published yet';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export function SoftwareUpdatesPanel() {
  const { data: softwareUpdate, isLoading: softwareLoading } = useSoftwareUpdateConfig();
  const updateSoftwareUpdate = useUpdateSoftwareUpdateConfig();
  const publishSoftwareUpdate = usePublishSoftwareUpdate();
  const uploadDesktopRelease = useUploadDesktopSoftwareUpdate();
  const uploadFileRef = useRef<HTMLInputElement>(null);

  const [version, setVersion] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [forceUpdate, setForceUpdate] = useState(false);
  const [releaseNotes, setReleaseNotes] = useState('');
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);

  useEffect(() => {
    if (!softwareUpdate) return;
    setVersion(softwareUpdate.version || '');
    setDownloadUrl(softwareUpdate.download_url || '');
    setForceUpdate(softwareUpdate.mandatory);
    setReleaseNotes(softwareUpdate.release_notes || '');
  }, [softwareUpdate]);

  const saveSoftwareUpdate = () => {
    if (!version.trim()) {
      toast({ title: 'Version is required', variant: 'destructive' });
      return;
    }
    updateSoftwareUpdate.mutate(
      {
        version: version.trim(),
        download_url: downloadUrl.trim(),
        mandatory: forceUpdate,
        release_notes: releaseNotes.trim(),
      },
      {
        onSuccess: () => toast({ title: 'Software update draft saved' }),
      },
    );
  };

  const publishUpdate = () => {
    publishSoftwareUpdate.mutate(undefined, {
      onSuccess: (result) =>
        toast({
          title: `Update ${result.version} published`,
          description: `Sent to ${result.recipients} active user(s).`,
        }),
      onError: (error: Error) =>
        toast({
          title: 'Unable to publish update',
          description: error.message,
          variant: 'destructive',
        }),
    });
  };

  const uploadInstaller = () => {
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
          const versionMatch = /^Camxora-(\d+(?:\.\d+){0,2})\./i.exec(result.filename);
          const parsedVersion = versionMatch?.[1];
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
            description: error.message,
            variant: 'destructive',
          }),
      },
    );
  };

  const useInstallerFile = (file: DesktopInstallerFile) => {
    setDownloadUrl(file.download_url);
    const versionMatch = /^Camxora-(\d+(?:\.\d+){0,2})\./i.exec(file.filename);
    const parsedVersion = versionMatch?.[1];
    if (parsedVersion) {
      setVersion(parsedVersion);
    }
    toast({
      title: 'Download URL applied',
      description: file.filename,
    });
  };

  return (
    <Card className="border-slate-800 bg-slate-900/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Download className="h-5 w-5 text-sky-400" />
          Software Update Release
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-slate-400">
          Publish a new desktop version to the notification bell. When users click Install update, Camxora
          silently downloads the package, applies it in the background, and restarts — no installer wizard.
        </p>
        {softwareLoading ? (
          <p className="text-sm text-slate-500">Loading software update settings…</p>
        ) : (
          <>
            <div className="space-y-2">
              <Label htmlFor="update-version">Version</Label>
              <Input
                id="update-version"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="2.5.0"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="update-download-url">Download URL</Label>
              <Input
                id="update-download-url"
                value={downloadUrl}
                onChange={(e) => setDownloadUrl(e.target.value)}
                placeholder="https://downloads.camxora.com/desktop/Camxora-2.5.0.zip"
              />
              <p className="text-xs text-slate-500">
                Recommended: a <span className="text-slate-400">.zip</span> of the full PyInstaller app folder
                for fully silent updates. Inno Setup <span className="text-slate-400">.exe</span> and{' '}
                <span className="text-slate-400">.msi</span> packages are also supported with quiet install flags.
              </p>
              <div className="rounded-md border border-slate-800 bg-slate-950/40 p-3 space-y-3">
                <div>
                  <p className="text-sm font-medium text-slate-200">Upload installer</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Upload a hosted package here to auto-generate an absolute download URL and save it
                    to the draft. Uses the version field above for the stored filename when provided.
                  </p>
                </div>
                <Input
                  ref={uploadFileRef}
                  type="file"
                  accept=".zip,.exe,.msi,application/zip,application/vnd.microsoft.portable-executable,application/x-msi"
                />
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={uploadInstaller}
                    disabled={uploadDesktopRelease.isPending}
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
                </div>
              </div>
              <InstallerFilesTable
                activeDownloadUrl={downloadUrl}
                onUseInstaller={useInstallerFile}
              />
            </div>
            <div className="rounded-md border border-slate-800 px-3 py-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-slate-200">Force update</p>
                  <p className="mt-1 text-xs text-slate-500">
                    When enabled, desktop users on an older version are blocked until they install this release. They cannot dismiss the update or continue using the current app.
                  </p>
                </div>
                <input
                  id="update-force"
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900"
                  checked={forceUpdate}
                  onChange={(event) => setForceUpdate(event.target.checked)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="update-release-notes">Release notes</Label>
              <Textarea
                id="update-release-notes"
                value={releaseNotes}
                onChange={(e) => setReleaseNotes(e.target.value)}
                placeholder="Bug fixes, performance improvements, and new music workflow tools."
                rows={5}
              />
            </div>
            <p className="text-xs text-slate-500">
              Last published: {formatTimestamp(softwareUpdate?.published_at)}
            </p>
            <div className="flex flex-wrap gap-3">
              <Button
                variant="outline"
                onClick={saveSoftwareUpdate}
                disabled={updateSoftwareUpdate.isPending}
              >
                {updateSoftwareUpdate.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Save Draft
              </Button>
              <Button onClick={publishUpdate} disabled={publishSoftwareUpdate.isPending}>
                {publishSoftwareUpdate.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Publish Update Notification
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default function SoftwareUpdatesPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Software Updates</h1>
        <p className="text-sm text-slate-400">
          Manage desktop release versions, download links, and forced update rollout.
        </p>
      </div>
      <SoftwareUpdatesPanel />
    </div>
  );
}
