import React from 'react';

import { DataTable, type ColumnDef } from '@/components/data-table/data-table';
import { FilterBar } from '@/components/data-table/filter-bar';
import { ErrorState } from '@/components/shared/error-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useAuditLog } from '@/hooks/use-audit-log';
import type { AuditLogParams } from '@/types/api';
import { formatAdminDateTime } from '@/lib/format-datetime';
import type { AuditEntry } from '@/types/models';

const PAGE_SIZE = 50;

function getActorLabel(entry: AuditEntry): string {
  return entry.actor_label ?? entry.actor_display_name ?? entry.actor_email ?? entry.actor_id ?? 'System';
}

function formatCreditImpact(value: number): string {
  if (value === 0) return '0';
  return value > 0 ? `-${value}` : `+${Math.abs(value)}`;
}

function renderActorCell(entry: AuditEntry) {
  return (
    <div className="min-w-0">
      <div className="truncate text-sm font-medium text-slate-100">{getActorLabel(entry)}</div>
      <div className="truncate text-xs text-slate-400">
        {entry.actor_email ?? entry.actor_role ?? 'Unknown actor'}
      </div>
    </div>
  );
}

function renderCreditCell(entry: AuditEntry) {
  return (
    <div className="min-w-0">
      <div
        className={`text-sm ${entry.credits_involved ? 'text-slate-100' : 'text-slate-400'}`}
      >
        {entry.credits_involved ? entry.credit_summary : 'No credit activity'}
      </div>
      <div className="text-xs text-slate-500">
        Recorded impact: {formatCreditImpact(entry.credit_impact)}
      </div>
    </div>
  );
}

const columns: ColumnDef<AuditEntry>[] = [
  {
    id: 'timestamp',
    header: 'Timestamp',
    accessorFn: (row) => formatAdminDateTime(row.created_at),
  },
  {
    id: 'actor',
    header: 'Performed By',
    accessorFn: (row) => renderActorCell(row),
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
    id: 'endpoint_path',
    header: 'Endpoint',
    accessorFn: (row) => (
      <span className="font-mono text-xs text-slate-400">
        {row.endpoint_path ?? '—'}
      </span>
    ),
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
    header: 'Credits',
    accessorFn: (row) => renderCreditCell(row),
  },
];

function renderMetadata(metadata: Record<string, unknown> | null): string {
  if (!metadata) return 'No metadata recorded.';
  try {
    return JSON.stringify(metadata, null, 2);
  } catch {
    return String(metadata);
  }
}

export default function AuditLogPage() {
  const [page, setPage] = React.useState(1);
  const [actorId, setActorId] = React.useState('');
  const [actionType, setActionType] = React.useState('');
  const [resourceType, setResourceType] = React.useState('');
  const [outcome, setOutcome] = React.useState<'all' | 'success' | 'failure'>('all');
  const [endpointPath, setEndpointPath] = React.useState('');
  const [fromDate, setFromDate] = React.useState('');
  const [toDate, setToDate] = React.useState('');
  const [selectedEntry, setSelectedEntry] = React.useState<AuditEntry | null>(null);

  const params: AuditLogParams = {
    page,
    page_size: PAGE_SIZE,
    ...(actorId && { actor_id: actorId }),
    ...(actionType && { action_type: actionType }),
    ...(resourceType && { resource_type: resourceType }),
    ...(outcome !== 'all' && { outcome }),
    ...(endpointPath && { endpoint_path: endpointPath }),
    ...(fromDate && { from_date: fromDate }),
    ...(toDate && { to_date: toDate }),
  };

  const { data, isLoading, isError, error, refetch } = useAuditLog(params);

  const resetPage = () => setPage(1);
  const clearFilters = () => {
    setActorId('');
    setActionType('');
    setResourceType('');
    setOutcome('all');
    setEndpointPath('');
    setFromDate('');
    setToDate('');
    setPage(1);
  };

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

      <p className="mb-4 text-sm text-slate-400">
        State-changing API requests and wallet credit events (pack purchases, redeem codes, admin
        adjusts). Per-generation credit debits are listed under{' '}
        <span className="text-slate-300">Usage</span>, not here.
      </p>

      <DataTable<AuditEntry>
        columns={columns}
        data={data?.items ?? []}
        totalCount={data?.total ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        isLoading={isLoading}
        onRowClick={(row) => setSelectedEntry(row)}
        filterBar={
          <FilterBar>
            <Input
              placeholder="Actor ID"
              value={actorId}
              onChange={(e) => {
                setActorId(e.target.value);
                resetPage();
              }}
              className="w-44"
            />
            <Input
              placeholder="Action Type (e.g. credit.redeem)"
              value={actionType}
              onChange={(e) => {
                setActionType(e.target.value);
                resetPage();
              }}
              className="w-52"
            />
            <Select
              value={actionType || 'all'}
              onValueChange={(value) => {
                setActionType(value === 'all' ? '' : value);
                resetPage();
              }}
            >
              <SelectTrigger className="w-52">
                <SelectValue placeholder="Credit events" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All action types</SelectItem>
                <SelectItem value="credit.pack.purchase">Credit pack purchase</SelectItem>
                <SelectItem value="credit.redeem">Redeem code</SelectItem>
                <SelectItem value="credit.adjust">Admin adjust</SelectItem>
                <SelectItem value="credit.pack.checkout">Pack checkout started</SelectItem>
              </SelectContent>
            </Select>
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
              placeholder="Endpoint"
              value={endpointPath}
              onChange={(e) => {
                setEndpointPath(e.target.value);
                resetPage();
              }}
              className="w-48"
            />
            <Select
              value={outcome}
              onValueChange={(value: 'all' | 'success' | 'failure') => {
                setOutcome(value);
                resetPage();
              }}
            >
              <SelectTrigger className="w-40 bg-slate-950 text-slate-200">
                <SelectValue placeholder="Outcome" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All outcomes</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="failure">Failure</SelectItem>
              </SelectContent>
            </Select>
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
            <Button variant="outline" onClick={clearFilters}>
              Reset filters
            </Button>
          </FilterBar>
        }
      />

      <Dialog open={Boolean(selectedEntry)} onOpenChange={(open) => !open && setSelectedEntry(null)}>
        <DialogContent className="max-w-3xl border-slate-800 bg-slate-950 text-slate-100">
          <DialogHeader>
            <DialogTitle>Audit Entry Detail</DialogTitle>
            <DialogDescription className="text-slate-400">
              Review the full context recorded for this audit event.
            </DialogDescription>
          </DialogHeader>
          {selectedEntry ? (
            <div className="grid gap-4">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Timestamp</div>
                  <div className="mt-1 text-sm text-slate-200">
                    {formatAdminDateTime(selectedEntry.created_at)}
                  </div>
                </div>
                <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Outcome</div>
                  <div className="mt-1">
                    <Badge
                      className={
                        selectedEntry.outcome === 'success'
                          ? 'border-transparent bg-green-600/20 text-green-400'
                          : 'border-transparent bg-red-600/20 text-red-400'
                      }
                    >
                      {selectedEntry.outcome}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Performed By</div>
                  <div className="mt-1 text-sm text-slate-200">{getActorLabel(selectedEntry)}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {selectedEntry.actor_email ?? 'No email recorded'}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span>Role: {selectedEntry.actor_role ?? 'unknown'}</span>
                    <span>ID: {selectedEntry.actor_id ?? 'system'}</span>
                  </div>
                </div>
                <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Action</div>
                  <div className="mt-1 text-sm text-slate-200">{selectedEntry.action_type}</div>
                </div>
                <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Target Resource</div>
                  <div className="mt-1 break-all text-sm text-slate-200">
                    {selectedEntry.target_resource ?? '—'}
                  </div>
                </div>
                <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Credits</div>
                  <div className="mt-1 text-sm text-slate-200">{selectedEntry.credit_summary}</div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span>Involved: {selectedEntry.credits_involved ? 'yes' : 'no'}</span>
                    <span>Direction: {selectedEntry.credit_direction ?? 'none'}</span>
                    <span>Recorded impact: {formatCreditImpact(selectedEntry.credit_impact)}</span>
                  </div>
                  {selectedEntry.credit_reason ? (
                    <div className="mt-2 text-xs text-slate-400">
                      Reason: {selectedEntry.credit_reason}
                    </div>
                  ) : null}
                  {selectedEntry.credit_reference ? (
                    <div className="mt-1 break-all text-xs text-slate-400">
                      Reference: {selectedEntry.credit_reference}
                    </div>
                  ) : null}
                  {selectedEntry.payment_reference ? (
                    <div className="mt-1 break-all text-xs text-slate-400">
                      Payment ref: {selectedEntry.payment_reference}
                    </div>
                  ) : null}
                </div>
                <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Source IP</div>
                  <div className="mt-1 font-mono text-xs text-slate-200">
                    {selectedEntry.source_ip ?? '—'}
                  </div>
                </div>
                <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Client ID</div>
                  <div className="mt-1 break-all font-mono text-xs text-slate-200">
                    {selectedEntry.client_id ?? '—'}
                  </div>
                </div>
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
                <div className="text-xs uppercase tracking-wide text-slate-500">Endpoint</div>
                <div className="mt-1 break-all font-mono text-xs text-slate-200">
                  {selectedEntry.endpoint_path ?? '—'}
                </div>
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
                <div className="text-xs uppercase tracking-wide text-slate-500">Metadata</div>
                <pre className="mt-2 max-h-[360px] overflow-auto whitespace-pre-wrap rounded bg-black/40 p-3 font-mono text-xs text-slate-200">
                  {renderMetadata(selectedEntry.metadata)}
                </pre>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
