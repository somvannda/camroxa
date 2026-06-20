import { useState } from 'react';
import { Plus, Settings, Key } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { KeyEntryRow } from '@/components/key-pool/key-entry-row';
import { ProviderSettings } from '@/components/key-pool/provider-settings';
import { AddKeyDialog } from '@/components/key-pool/add-key-dialog';
import { EditKeyDialog } from '@/components/key-pool/edit-key-dialog';
import { DeleteConfirmDialog } from '@/components/key-pool/delete-confirm-dialog';
import { useProviderKeys } from '@/hooks/use-key-pool';
import type { ApiKeyEntry } from '@/types/key-pool';

interface ProviderTabProps {
  provider: string;
}

export function ProviderTab({ provider }: ProviderTabProps) {
  const [showSettings, setShowSettings] = useState(false);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [editEntry, setEditEntry] = useState<ApiKeyEntry | null>(null);
  const [deleteEntry, setDeleteEntry] = useState<ApiKeyEntry | null>(null);
  const { data: keys, isLoading, isError, error, refetch } = useProviderKeys(provider);

  function handleEdit(entry: ApiKeyEntry) {
    setEditEntry(entry);
  }

  function handleDeleteConfirm(entry: ApiKeyEntry) {
    setDeleteEntry(entry);
  }

  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-9" />
        </div>
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-4 p-8 text-center">
        <p className="text-sm text-red-400">
          Failed to load keys: {error?.message ?? 'Unknown error'}
        </p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      {/* Header with actions */}
      <div className="flex items-center justify-between">
        <Button size="sm" className="gap-1.5" onClick={() => setShowAddDialog(true)}>
          <Plus className="h-4 w-4" />
          Add Key
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setShowSettings(!showSettings)}
          aria-label="Provider settings"
        >
          <Settings className="h-4 w-4 text-slate-400" />
        </Button>
      </div>

      {/* Provider settings panel */}
      {showSettings && <ProviderSettings provider={provider} />}

      {/* Key list */}
      {keys && keys.length > 0 ? (
        <div className="space-y-2">
          {keys.map((entry) => (
            <KeyEntryRow
              key={entry.id}
              entry={entry}
              provider={provider}
              onEdit={handleEdit}
              onDeleteConfirm={handleDeleteConfirm}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-navy-700 py-12 text-center">
          <Key className="h-8 w-8 text-slate-500" />
          <p className="text-sm text-slate-400">
            No API keys configured for this provider.
          </p>
          <p className="text-xs text-slate-500">
            Click &quot;Add Key&quot; to get started.
          </p>
        </div>
      )}

      {/* Dialogs */}
      <AddKeyDialog
        provider={provider}
        open={showAddDialog}
        onOpenChange={setShowAddDialog}
      />
      <EditKeyDialog
        provider={provider}
        entry={editEntry}
        open={editEntry !== null}
        onOpenChange={(open) => { if (!open) setEditEntry(null); }}
      />
      <DeleteConfirmDialog
        provider={provider}
        entry={deleteEntry}
        open={deleteEntry !== null}
        onOpenChange={(open) => { if (!open) setDeleteEntry(null); }}
      />
    </div>
  );
}
