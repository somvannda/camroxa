import React from 'react';

import { DataTable, type ColumnDef } from '@/components/data-table/data-table';
import { FilterBar } from '@/components/data-table/filter-bar';
import { ErrorState } from '@/components/shared/error-state';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useAuditLog } from '@/hooks/use-audit-log';
import type { AuditLogParams } from '@/types/api';
import type { AuditEntry } from '@/types/models';

const PAGE_SIZE = 50;

const columns: ColumnDef<AuditEntry>[] = [
  {
    id: 'timestamp',
    header: 'Timestamp',
    accessorFn: (row) => new Date(row.created_at).toLocaleString(),
  },
  {
    id: 'actor',
    header: 'Actor',
    accessorFn: (row) => row.actor_id ?? '—',
  },
  {
    id: 'action_type',
    header: 'Action Type',
    accessorFn: (row) => row.action_type,
  },
  {
    id: 'target_resource',
    header: 'Target Resource',
    accessorFn: (row) => row.target_resource ?? '—',
  },
  {
    id: 'outcome',
    header: 'Outcome',
    accessorFn: (row) => (
      <Badge
        className={
          row.outcome === 'success'
            ? 'border-transparent bg-green-600/20 text-green-400'
            : 'border-transparent bg-red-600/20 text-red-400'
        }
      >
        {row.outcome}
      </Badge>
    ),
  },
  {
    id: 'credit_impact',
    header: 'Credit Impact',
    accessorFn: (row) => {
      if (row.credit_impact === 0) return null;
      const isPositive = row.credit_impact > 0;
      return (
        <span className={isPositive ? 'text-green-400' : 'text-red-400'}>
          {isPositive ? `+${row.credit_impact}` : row.credit_impact}
        </span>
      );
    },
  },
];

export default function AuditLogPage() {
  const [page, setPage] = React.useState(1);
  const [actorId, setActorId] = React.useState('');
  const [actionType, setActionType] = React.useState('');
  const [resourceType, setResourceType] = React.useState('');
  const [fromDate, setFromDate] = React.useState('');
  const [toDate, setToDate] = React.useState('');

  const params: AuditLogParams = {
    page,
    page_size: PAGE_SIZE,
    ...(actorId && { actor_id: actorId }),
    ...(actionType && { action_type: actionType }),
    ...(resourceType && { resource_type: resourceType }),
    ...(fromDate && { from_date: fromDate }),
    ...(toDate && { to_date: toDate }),
  };

  const { data, isLoading, isError, error, refetch } = useAuditLog(params);

  const resetPage = () => setPage(1);

  if (isError) {
    return (
      <div className="p-6">
        <h1 className="mb-6 text-2xl font-bold text-slate-100">Audit Log</h1>
        <ErrorState
          message={(error as Error)?.message ?? 'Failed to load audit log'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="mb-6 text-2xl font-bold text-slate-100">Audit Log</h1>

      <DataTable<AuditEntry>
        columns={columns}
        data={data?.items ?? []}
        totalCount={data?.total ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        isLoading={isLoading}
        filterBar={
          <FilterBar>
            <Input
              placeholder="Actor ID"
              value={actorId}
              onChange={(e) => {
                setActorId(e.target.value);
                resetPage();
              }}
              className="w-40"
            />
            <Input
              placeholder="Action Type"
              value={actionType}
              onChange={(e) => {
                setActionType(e.target.value);
                resetPage();
              }}
              className="w-40"
            />
            <Input
              placeholder="Resource Type"
              value={resourceType}
              onChange={(e) => {
                setResourceType(e.target.value);
                resetPage();
              }}
              className="w-40"
            />
            <Input
              type="date"
              value={fromDate}
              onChange={(e) => {
                setFromDate(e.target.value);
                resetPage();
              }}
              className="w-40"
            />
            <Input
              type="date"
              value={toDate}
              onChange={(e) => {
                setToDate(e.target.value);
                resetPage();
              }}
              className="w-40"
            />
          </FilterBar>
        }
      />
    </div>
  );
}
