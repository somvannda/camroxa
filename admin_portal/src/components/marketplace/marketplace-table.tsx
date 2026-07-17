/**
 * Marketplace table component with status toggle and delete actions.
 * Provides optimistic UI updates with rollback on API error.
 */

import { useState } from 'react';
import { Trash2 } from 'lucide-react';

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
import { useDeleteItem, useToggleStatus } from '@/hooks/use-marketplace';
import { toast } from '@/hooks/use-toast';
import type { MarketplaceItem } from '@/types/marketplace';

// --- Style Maps ---

const KIND_CLASSES: Record<MarketplaceItem['kind'], string> = {
  video: 'border-sky-400/25 bg-sky-500/10 text-sky-200',
  reel: 'border-purple-400/25 bg-purple-500/10 text-purple-200',
};

// --- Sub-Components ---

interface StatusToggleProps {
  item: MarketplaceItem;
}

function StatusToggle({ item }: StatusToggleProps) {
  const [optimisticStatus, setOptimisticStatus] = useState(item.status);
  const toggleMutation = useToggleStatus(item.id);

  // Sync optimistic state when item prop changes (e.g. after query invalidation)
  if (optimisticStatus !== item.status && !toggleMutation.isPending) {
    setOptimisticStatus(item.status);
  }

  const isEnabled = optimisticStatus === 'enabled';

  const handleToggle = () => {
    const newStatus: 'enabled' | 'disabled' = isEnabled ? 'disabled' : 'enabled';
    setOptimisticStatus(newStatus);

    toggleMutation.mutate(newStatus, {
      onError: () => {
        // Revert on error
        setOptimisticStatus(item.status);
        toast({
          variant: 'destructive',
          title: 'Toggle failed',
          description: `Failed to ${newStatus === 'enabled' ? 'enable' : 'disable'} "${item.name}". Please try again.`,
        });
      },
    });
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isEnabled}
      aria-label={`${isEnabled ? 'Disable' : 'Enable'} ${item.name}`}
      disabled={toggleMutation.isPending}
      onClick={handleToggle}
      className={`
        relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full
        border-2 border-transparent transition-colors duration-200
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
        disabled:cursor-not-allowed disabled:opacity-50
        ${isEnabled ? 'bg-green-500/80' : 'bg-slate-700'}
      `}
    >
      <span
        className={`
          pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg ring-0 transition-transform duration-200
          ${isEnabled ? 'translate-x-5' : 'translate-x-1'}
        `}
      />
    </button>
  );
}

interface DeleteActionProps {
  item: MarketplaceItem;
}

function DeleteAction({ item }: DeleteActionProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const deleteMutation = useDeleteItem(item.id);

  const handleDelete = () => {
    deleteMutation.mutate(undefined, {
      onSuccess: () => {
        setConfirmOpen(false);
      },
      onError: () => {
        setConfirmOpen(false);
        toast({
          variant: 'destructive',
          title: 'Delete failed',
          description: `Failed to delete "${item.name}". Please try again.`,
        });
      },
    });
  };

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label={`Delete ${item.name}`}
        onClick={() => setConfirmOpen(true)}
        className="text-slate-400 hover:text-red-400"
      >
        <Trash2 className="h-4 w-4" />
      </Button>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Delete Template"
        description={`Are you sure you want to delete '${item.name}'? This action cannot be undone.`}
        onConfirm={handleDelete}
        variant="destructive"
        confirmText="Delete"
        isLoading={deleteMutation.isPending}
      />
    </>
  );
}

// --- Main Component ---

interface MarketplaceTableProps {
  items: MarketplaceItem[];
  isLoading: boolean;
}

export function MarketplaceTable({ items, isLoading }: MarketplaceTableProps) {
  if (isLoading) {
    return (
      <div className="rounded-md border border-slate-800">
        <Table>
          <TableHeader>
            <TableRow className="border-slate-800 bg-slate-900 hover:bg-slate-900">
              <TableHead>Name</TableHead>
              <TableHead>Kind</TableHead>
              <TableHead>Author</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={`skeleton-${i}`} className="border-slate-800 bg-slate-950">
                <TableCell><Skeleton className="h-5 w-32 bg-slate-800" /></TableCell>
                <TableCell><Skeleton className="h-5 w-14 bg-slate-800" /></TableCell>
                <TableCell><Skeleton className="h-5 w-20 bg-slate-800" /></TableCell>
                <TableCell><Skeleton className="h-5 w-12 bg-slate-800" /></TableCell>
                <TableCell><Skeleton className="h-6 w-11 rounded-full bg-slate-800" /></TableCell>
                <TableCell><Skeleton className="h-8 w-8 bg-slate-800" /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-md border border-slate-800">
        <Table>
          <TableHeader>
            <TableRow className="border-slate-800 bg-slate-900 hover:bg-slate-900">
              <TableHead>Name</TableHead>
              <TableHead>Kind</TableHead>
              <TableHead>Author</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow className="border-slate-800 bg-slate-950">
              <TableCell colSpan={6} className="h-24 text-center text-slate-400">
                No marketplace templates found.
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-slate-800">
      <Table>
        <TableHeader>
          <TableRow className="border-slate-800 bg-slate-900 hover:bg-slate-900">
            <TableHead>Name</TableHead>
            <TableHead>Kind</TableHead>
            <TableHead>Author</TableHead>
            <TableHead>Version</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.id} className="border-slate-800 bg-slate-950 hover:bg-slate-800">
              <TableCell>
                <span className="font-medium text-slate-100">{item.name}</span>
              </TableCell>
              <TableCell>
                <Badge variant="outline" className={KIND_CLASSES[item.kind]}>
                  {item.kind}
                </Badge>
              </TableCell>
              <TableCell>
                <span className="text-slate-300">{item.author}</span>
              </TableCell>
              <TableCell>
                <span className="text-slate-400">{item.version}</span>
              </TableCell>
              <TableCell>
                <StatusToggle item={item} />
              </TableCell>
              <TableCell>
                <DeleteAction item={item} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
