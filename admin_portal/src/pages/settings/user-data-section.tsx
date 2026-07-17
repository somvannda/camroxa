import { useState } from 'react';
import { AlertTriangle, Database, Loader2, RotateCcw } from 'lucide-react';

import {
  useBackupList,
  useResetUserData,
  useRestoreUserData,
} from '@/hooks/use-user-data-reset';
import { toast } from '@/hooks/use-toast';
import { PasswordConfirmDialog } from '@/components/shared/password-confirm-dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import type { BackupEntry } from '@/types/user-data-reset';

type DialogMode = 'reset' | 'restore' | null;

/**
 * Format bytes to a human-readable string (KB, MB, GB).
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

/**
 * Format ISO timestamp to a human-readable date/time string.
 */
function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * User Data Management section for the Settings page.
 * Provides destructive reset functionality and backup/restore controls.
 */
export function UserDataManagementSection() {
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [selectedBackup, setSelectedBackup] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const { data: backups, isLoading, isError, error, refetch } = useBackupList();
  const resetMutation = useResetUserData();
  const restoreMutation = useRestoreUserData();

  const isOperationInProgress = resetMutation.isPending || restoreMutation.isPending;

  const handleResetClick = () => {
    setPasswordError(null);
    setDialogMode('reset');
  };

  const handleRestoreClick = (filename: string) => {
    setPasswordError(null);
    setSelectedBackup(filename);
    setDialogMode('restore');
  };

  const handleDialogClose = (open: boolean) => {
    if (!open) {
      setDialogMode(null);
      setSelectedBackup(null);
      setPasswordError(null);
    }
  };

  const handleConfirm = (password: string) => {
    setPasswordError(null);

    if (dialogMode === 'reset') {
      resetMutation.mutate(
        { password },
        {
          onSuccess: () => {
            setDialogMode(null);
            toast({
              title: 'User data reset complete',
              description: 'All user data has been wiped. A backup was created automatically.',
              duration: 5000,
            });
          },
          onError: (err) => {
            const message = err instanceof Error ? err.message : 'Reset failed. Please try again.';
            if (message.toLowerCase().includes('credentials') || message.toLowerCase().includes('password')) {
              setPasswordError(message);
            } else {
              setDialogMode(null);
              toast({
                title: 'Reset failed',
                description: message,
                variant: 'destructive',
              });
            }
          },
        },
      );
    } else if (dialogMode === 'restore' && selectedBackup) {
      restoreMutation.mutate(
        { backup_filename: selectedBackup, password },
        {
          onSuccess: (result) => {
            setDialogMode(null);
            setSelectedBackup(null);
            toast({
              title: 'Restore complete',
              description: `${result.records_restored} records restored, ${result.records_skipped} skipped.`,
              duration: 5000,
            });
          },
          onError: (err) => {
            const message = err instanceof Error ? err.message : 'Restore failed. Please try again.';
            if (message.toLowerCase().includes('credentials') || message.toLowerCase().includes('password')) {
              setPasswordError(message);
            } else {
              setDialogMode(null);
              setSelectedBackup(null);
              toast({
                title: 'Restore failed',
                description: message,
                variant: 'destructive',
              });
            }
          },
        },
      );
    }
  };

  return (
    <div className="space-y-6">
      {/* Reset Section */}
      <Card className="border-red-500/20 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg text-slate-100">
            <Database className="h-5 w-5 text-red-400" />
            User Data Management
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-red-500/20 bg-red-950/20 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-red-300">
                  Destructive Action
                </p>
                <p className="text-sm text-slate-400">
                  Resetting user data will permanently delete all user accounts, sessions,
                  credits, transactions, and associated data. A backup is created automatically
                  before the reset. The admin account and system configuration are preserved.
                </p>
              </div>
            </div>
          </div>

          <Button
            variant="destructive"
            onClick={handleResetClick}
            disabled={isOperationInProgress}
          >
            {resetMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Reset All User Data
          </Button>
        </CardContent>
      </Card>

      {/* Backups Section */}
      <Card className="border-slate-800 bg-slate-900/50">
        <CardHeader>
          <CardTitle className="text-lg text-slate-100">Available Backups</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="space-y-3">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          )}

          {isError && (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <p className="text-sm text-red-400">
                {error instanceof Error ? error.message : 'Failed to load backup list.'}
              </p>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                <RotateCcw className="mr-2 h-4 w-4" />
                Retry
              </Button>
            </div>
          )}

          {!isLoading && !isError && backups && backups.length === 0 && (
            <p className="py-6 text-center text-sm text-slate-400">
              No backups available. A backup is created automatically before each reset.
            </p>
          )}

          {!isLoading && !isError && backups && backups.length > 0 && (
            <div className="space-y-2">
              {backups.map((backup: BackupEntry) => (
                <div
                  key={backup.filename}
                  className="flex items-center justify-between gap-4 rounded-md border border-slate-700 p-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-200">
                      {formatTimestamp(backup.created_at)}
                    </p>
                    <p className="text-xs text-slate-400">
                      {formatBytes(backup.file_size_bytes)} · {backup.total_records} records
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRestoreClick(backup.filename)}
                    disabled={isOperationInProgress}
                  >
                    {restoreMutation.isPending && selectedBackup === backup.filename && (
                      <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                    )}
                    Restore
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Password Confirmation Dialog */}
      <PasswordConfirmDialog
        open={dialogMode !== null}
        onOpenChange={handleDialogClose}
        title={dialogMode === 'reset' ? 'Confirm User Data Reset' : 'Confirm Data Restore'}
        description={
          dialogMode === 'reset'
            ? 'This action will delete all user data. A backup will be created automatically. Enter your password to confirm.'
            : `Restore data from backup. This will insert records that don't already exist. Enter your password to confirm.`
        }
        onConfirm={handleConfirm}
        isLoading={isOperationInProgress}
        error={passwordError}
      />
    </div>
  );
}
