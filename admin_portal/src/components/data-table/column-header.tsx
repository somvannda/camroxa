import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export type SortDirection = 'asc' | 'desc' | null;

interface ColumnHeaderProps {
  title: string;
  sortable?: boolean;
  sortDirection?: SortDirection;
  onSort?: () => void;
}

export function ColumnHeader({
  title,
  sortable = false,
  sortDirection = null,
  onSort,
}: ColumnHeaderProps) {
  if (!sortable) {
    return <span className="text-slate-300 font-medium">{title}</span>;
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      className={cn(
        '-ml-3 h-8 text-slate-300 hover:text-slate-100 hover:bg-slate-800',
        sortDirection && 'text-slate-100'
      )}
      onClick={onSort}
    >
      {title}
      {sortDirection === 'asc' ? (
        <ArrowUp className="ml-1 h-4 w-4" />
      ) : sortDirection === 'desc' ? (
        <ArrowDown className="ml-1 h-4 w-4" />
      ) : (
        <ArrowUpDown className="ml-1 h-4 w-4" />
      )}
    </Button>
  );
}
