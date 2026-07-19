import { useState } from 'react';
import { Copy, Loader2, Trash2 } from 'lucide-react';

import { ConfirmDialog } from '@/components/shared/confirm-dialog';
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
  type DesktopInstallerFile,
} from '@/hooks/use-desktop-notifications';
import { toast } from '@/hooks/use-toast';

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
  const match = /^Camxora-(\d+(?:\.\d+){0,2})\./i.exec(filename);
  return match?.[1] ?? null;
}

interface InstallerFilesTableProps {
  activeDownloadUrl?: string;
  onUseInstaller: (file: DesktopInstallerFile) => void;
}

export function InstallerFilesTable({ activeDownloadUrl, onUseInstaller }: InstallerFilesTableProps) {
  const { data, isLoading } = useDesktopInstallers();
  const deleteInstaller = useDeleteDesktopInstaller();
  const [pendingDelete, setPendingDelete] = useState<DesktopInstallerFile | null>(null);

  const copyUrl = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      toast({ title: 'Download URL copied' });
    } catch {
      toast({ title: 'Unable to copy URL', variant: 'destructive' });
    }
  };

  const items = data?.items ?? [];

  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-medium text-slate-200">Uploaded installers</p>
        <p className="mt-1 text-xs text-slate-500">
          Hosted packages on this server. Upload auto-generates an absolute download URL and saves it
          to the draft.
        </p>
      </div>

      {isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">No installer files uploaded yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-slate-800">
          <Table>
            <TableHeader>
              <TableRow className="border-slate-800 hover:bg-transparent">
                <TableHead className="text-slate-400">File</TableHead>
                <TableHead className="text-slate-400">Size</TableHead>
                <TableHead className="text-slate-400">Uploaded</TableHead>
                <TableHead className="text-slate-400">Download URL</TableHead>
                <TableHead className="text-right text-slate-400">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => {
                const isActive = Boolean(activeDownloadUrl && activeDownloadUrl === item.download_url);
                const versionHint = extractVersionFromFilename(item.filename);
                return (
                  <TableRow key={item.filename} className="border-slate-800">
                    <TableCell className="font-medium text-slate-200">
                      <div>{item.filename}</div>
                      {versionHint ? (
                        <p className="text-xs text-slate-500">Version {versionHint}</p>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-slate-300">{formatBytes(item.size_bytes)}</TableCell>
                    <TableCell className="text-slate-400">{formatTimestamp(item.modified_at)}</TableCell>
                    <TableCell className="max-w-xs truncate text-xs text-slate-400">
                      {item.download_url}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant={isActive ? 'default' : 'outline'}
                          onClick={() => onUseInstaller(item)}
                        >
                          {isActive ? 'In use' : 'Use'}
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
        open={Boolean(pendingDelete)}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
        title="Delete installer file?"
        description={
          pendingDelete
            ? `Remove ${pendingDelete.filename} from server storage. This cannot be undone.`
            : ''
        }
        confirmText="Delete"
        variant="destructive"
        isLoading={deleteInstaller.isPending}
        onConfirm={() => {
          if (!pendingDelete) return;
          deleteInstaller.mutate(pendingDelete.filename, {
            onSuccess: () => {
              toast({ title: `${pendingDelete.filename} deleted` });
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

      {deleteInstaller.isPending ? (
        <p className="flex items-center gap-2 text-xs text-slate-500">
          <Loader2 className="h-3 w-3 animate-spin" />
          Deleting installer…
        </p>
      ) : null}
    </div>
  );
}
