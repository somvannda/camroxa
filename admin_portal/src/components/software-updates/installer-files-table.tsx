import { useState } from 'react';
import { Copy, Rocket, Trash2 } from 'lucide-react';

import { ConfirmDialog } from '@/components/shared/confirm-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  useDeleteDesktopInstaller,
  useDesktopInstallers,
  useDraftDesktopInstaller,
  useSoftwareUpdateConfig,
  type DesktopInstallerFile,
} from '@/hooks/use-desktop-notifications';
import { toast } from '@/hooks/use-toast';

function formatDownloadCount(value: number | undefined) {
  const count = Math.max(0, Number(value ?? 0));
  return new Intl.NumberFormat('en-US').format(count);
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTimestamp(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function extractVersionFromFilename(filename: string) {
  const match =
    /^(?:CamxoraSetup-|Camxora-Setup-|Camxora-)(\d+(?:\.\d+){0,2})(?:-(?:production|sandbox))?\./i.exec(
      filename,
    );
  return match?.[1] ?? null;
}

function restoredToastDescription(restored: string | null | undefined, unpublished: string | undefined) {
  if (restored) {
    return `Public download, changelog, and force update reverted to ${restored}.`;
  }
  if (unpublished) {
    return `${unpublished} is no longer live. No previous release was available to restore.`;
  }
  return undefined;
}

interface InstallerFilesTableProps {
  onPublishClick: (file: DesktopInstallerFile) => void;
  onDraftClick: (file: DesktopInstallerFile) => void;
}

export function InstallerFilesTable({ onPublishClick, onDraftClick }: InstallerFilesTableProps) {
  const { data: softwareUpdate } = useSoftwareUpdateConfig();
  const { data, isLoading } = useDesktopInstallers();
  const deleteInstaller = useDeleteDesktopInstaller();
  const draftInstaller = useDraftDesktopInstaller();
  const [pendingDelete, setPendingDelete] = useState<DesktopInstallerFile | null>(null);
  const [pendingLiveDraft, setPendingLiveDraft] = useState<DesktopInstallerFile | null>(null);

  const liveDownloadUrl = softwareUpdate?.live_download_url || '';
  const liveVersion = softwareUpdate?.live_version || '';
  const hasLive = Boolean(liveVersion || liveDownloadUrl);

  const copyUrl = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      toast({ title: 'Download URL copied' });
    } catch {
      toast({ title: 'Unable to copy URL', variant: 'destructive' });
    }
  };

  const items = data?.items ?? [];

  const isLiveFile = (item: DesktopInstallerFile) => {
    const versionHint = extractVersionFromFilename(item.filename);
    if (liveDownloadUrl && liveDownloadUrl === item.download_url) return true;
    return Boolean(hasLive && liveVersion && versionHint && liveVersion === versionHint);
  };

  const handleDraftClick = (item: DesktopInstallerFile) => {
    if (isLiveFile(item)) {
      setPendingLiveDraft(item);
      return;
    }
    onDraftClick(item);
  };

  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-medium text-slate-200">Uploaded installers</p>
        <p className="mt-1 text-xs text-slate-500">
          Use <span className="text-slate-300">Publish</span> on a row to review settings and make that file
          the live release, or <span className="text-slate-300">Draft</span> to take a live release off
          /download (restoring the previous live version) or configure a non-live file as the current draft.
        </p>
      </div>

      {isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">No installer files uploaded yet. Create a new release to upload one.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-slate-800">
          <Table>
            <TableHeader>
              <TableRow className="border-slate-800 hover:bg-transparent">
                <TableHead className="text-slate-400">File</TableHead>
                <TableHead className="text-slate-400">Size</TableHead>
                <TableHead className="text-slate-400">Uploaded</TableHead>
                <TableHead className="text-slate-400">Downloads</TableHead>
                <TableHead className="text-slate-400">Status</TableHead>
                <TableHead className="text-right text-slate-400">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => {
                const versionHint = extractVersionFromFilename(item.filename);
                const isLiveRelease = isLiveFile(item);
                const isDraftSelection = Boolean(
                  softwareUpdate?.download_url && softwareUpdate.download_url === item.download_url,
                );

                return (
                  <TableRow key={item.filename} className="border-slate-800">
                    <TableCell className="font-medium text-slate-200">
                      <div>{item.filename}</div>
                      {versionHint ? <p className="text-xs text-slate-500">Version {versionHint}</p> : null}
                    </TableCell>
                    <TableCell className="text-slate-300">{formatBytes(item.size_bytes)}</TableCell>
                    <TableCell className="text-slate-400">{formatTimestamp(item.modified_at)}</TableCell>
                    <TableCell className="text-slate-300">{formatDownloadCount(item.download_count)}</TableCell>
                    <TableCell>
                      {isLiveRelease ? (
                        <Badge>Live</Badge>
                      ) : isDraftSelection ? (
                        <Badge variant="secondary">Draft</Badge>
                      ) : (
                        <span className="text-xs text-slate-500">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant={isLiveRelease ? 'default' : 'outline'}
                          onClick={() => onPublishClick(item)}
                        >
                          <Rocket className="mr-1 h-3 w-3" />
                          {isLiveRelease ? 'Republish' : 'Publish'}
                        </Button>
                        <Button type="button" size="sm" variant="ghost" onClick={() => handleDraftClick(item)}>
                          Draft
                        </Button>
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          aria-label={`Copy download URL for ${item.filename}`}
                          onClick={() => copyUrl(item.download_url)}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          aria-label={`Delete ${item.filename}`}
                          disabled={deleteInstaller.isPending}
                          onClick={() => setPendingDelete(item)}
                        >
                          <Trash2 className="h-4 w-4 text-red-400" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <ConfirmDialog
        open={Boolean(pendingLiveDraft)}
        onOpenChange={(open) => {
          if (!open) setPendingLiveDraft(null);
        }}
        title="Move live release back to draft?"
        description={
          pendingLiveDraft
            ? `Take ${pendingLiveDraft.filename} off /download. Website version, changelog, and force update will revert to the previous live release if one exists.`
            : ''
        }
        confirmText="Move to draft"
        isLoading={draftInstaller.isPending}
        onConfirm={() => {
          if (!pendingLiveDraft) return;
          const filename = pendingLiveDraft.filename;
          draftInstaller.mutate(filename, {
            onSuccess: (result) => {
              toast({
                title: `${filename} moved to draft`,
                description: restoredToastDescription(result.restored_live_version, result.unpublished_version),
              });
              setPendingLiveDraft(null);
            },
            onError: (error: Error) =>
              toast({
                title: 'Could not move to draft',
                description: error.message,
                variant: 'destructive',
              }),
          });
        }}
      />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
        title="Delete installer file?"
        description={
          pendingDelete
            ? isLiveFile(pendingDelete)
              ? `Remove ${pendingDelete.filename} from server storage. Because this is the live release, public download, changelog, and force update will revert to the previous live version if one exists. This cannot be undone.`
              : `Remove ${pendingDelete.filename} from server storage. This cannot be undone.`
            : ''
        }
        confirmText="Delete"
        variant="destructive"
        isLoading={deleteInstaller.isPending}
        onConfirm={() => {
          if (!pendingDelete) return;
          const filename = pendingDelete.filename;
          deleteInstaller.mutate(filename, {
            onSuccess: (result) => {
              toast({
                title: `${filename} deleted`,
                description: restoredToastDescription(result.restored_live_version, result.unpublished_version),
              });
              setPendingDelete(null);
            },
            onError: (error: Error) =>
              toast({
                title: 'Delete failed',
                description: error.message,
                variant: 'destructive',
              }),
          });
        }}
      />
    </div>
  );
}
