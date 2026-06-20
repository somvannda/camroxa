import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useDeleteKey } from '@/hooks/use-key-pool';
import type { ApiKeyEntry } from '@/types/key-pool';

interface DeleteConfirmDialogProps {
  provider: string;
  entry: ApiKeyEntry | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteConfirmDialog({
  provider,
  entry,
  open,
  onOpenChange,
}: DeleteConfirmDialogProps) {
  const deleteKey = useDeleteKey(provider);

  function handleDelete() {
    if (!entry) return;

    deleteKey.mutate(entry.id, {
      onSuccess: () => {
        onOpenChange(false);
      },
    });
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      deleteKey.reset();
    }
    onOpenChange(nextOpen);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete API Key</DialogTitle>
          <DialogDescription>
            This action cannot be undone.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <p className="text-sm">
            Are you sure you want to delete the key{' '}
            <span className="font-semibold">&ldquo;{entry?.label}&rdquo;</span>{' '}
            from the{' '}
            <span className="font-semibold">{provider}</span>{' '}
            provider?
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            The key will be permanently removed from the pool and any pending
            requests will be redistributed to remaining active keys.
          </p>
        </div>

        {deleteKey.isError && (
          <p className="text-sm text-destructive">
            {deleteKey.error?.message ?? 'Failed to delete key. Please try again.'}
          </p>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={deleteKey.isPending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={handleDelete}
            disabled={deleteKey.isPending}
          >
            {deleteKey.isPending ? 'Deleting...' : 'Delete Key'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
