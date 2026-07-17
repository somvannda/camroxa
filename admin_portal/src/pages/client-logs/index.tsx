import React from 'react';
import { useSearchParams } from 'react-router-dom';

import { DataTable, type ColumnDef } from '@/components/data-table/data-table';
import { FilterBar } from '@/components/data-table/filter-bar';
import { ErrorState } from '@/components/shared/error-state';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useClientLogBatch, useUserClientLogs } from '@/hooks/use-client-logs';
import { useUsers } from '@/hooks/use-users';
import type { ClientLogBatchSummary } from '@/types/models';
import type { User } from '@/types/models';
import type { UserListParams } from '@/types/api';

const PAGE_SIZE = 20;
const USER_PAGE_SIZE = 20;

const STATUS_BADGE_CLASSES: Record<User['status'], string> = {
  active: 'border-green-500/30 bg-green-500/10 text-green-400',
  suspended: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
  deleted: 'border-red-500/30 bg-red-500/10 text-red-400',
};

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

const columns: ColumnDef<ClientLogBatchSummary>[] = [
  {
    id: 'created_at',
    header: 'Synced',
    accessorFn: (row) => new Date(row.created_at).toLocaleString(),
  },
  {
    id: 'line_count',
    header: 'Lines',
    accessorFn: (row) => String(row.line_count),
  },
  {
    id: 'size_bytes',
    header: 'Size',
    accessorFn: (row) => formatBytes(row.size_bytes),
  },
  {
    id: 'app_version',
    header: 'App',
    accessorFn: (row) => row.app_version || '—',
  },
  {
    id: 'client_label',
    header: 'Client',
    accessorFn: (row) => row.client_label || row.client_id || '—',
  },
  {
    id: 'preview',
    header: 'Preview',
    accessorFn: (row) => (
      <span className="line-clamp-1 max-w-md font-mono text-xs text-slate-400">
        {row.preview || '—'}
      </span>
    ),
  },
];

const userColumns: ColumnDef<User>[] = [
  {
    id: 'email',
    header: 'Email',
    accessorFn: (row) => <span className="text-slate-200">{row.email}</span>,
    sortable: true,
  },
  {
    id: 'display_name',
    header: 'Display Name',
    accessorFn: (row) => <span className="text-slate-300">{row.display_name}</span>,
    sortable: true,
  },
  {
    id: 'status',
    header: 'Status',
    accessorFn: (row) => (
      <Badge variant="outline" className={STATUS_BADGE_CLASSES[row.status]}>
        {row.status}
      </Badge>
    ),
  },
  {
    id: 'plan_name',
    header: 'Plan',
    accessorFn: (row) =>
      row.plan_name ? (
        <span className="text-slate-200">{row.plan_name}</span>
      ) : (
        <span className="italic text-slate-500">No plan</span>
      ),
  },
  {
    id: 'channel_profile_count',
    header: 'Profiles',
    accessorFn: (row) => <span className="text-slate-300">{row.channel_profile_count}</span>,
  },
  {
    id: 'credit_balance',
    header: 'Credits',
    accessorFn: (row) => <span className="font-medium text-slate-200">{row.credit_balance.toLocaleString()} cr</span>,
  },
  {
    id: 'created_at',
    header: 'Registered',
    accessorFn: (row) => <span className="text-slate-400">{new Date(row.created_at).toLocaleDateString()}</span>,
    sortable: true,
  },
];

export default function ClientLogsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [userPage, setUserPage] = React.useState(1);
  const [logPage, setLogPage] = React.useState(1);
  const [selectedBatchId, setSelectedBatchId] = React.useState<string | null>(null);
  const [selectedUser, setSelectedUser] = React.useState<User | null>(null);
  const [selectedUserId, setSelectedUserId] = React.useState(searchParams.get('userId') || '');
  const [userSearch, setUserSearch] = React.useState('');

  const userParams: UserListParams = {
    page: userPage,
    page_size: USER_PAGE_SIZE,
  };

  const usersQuery = useUsers(userParams);
  const users = usersQuery.data?.items ?? [];
  const visibleUsers = React.useMemo(() => {
    const keyword = userSearch.trim().toLowerCase();
    if (!keyword) return users;
    return users.filter((user) => {
      return (
        user.email.toLowerCase().includes(keyword) ||
        user.display_name.toLowerCase().includes(keyword) ||
        user.id.toLowerCase().includes(keyword)
      );
    });
  }, [userSearch, users]);

  const listQuery = useUserClientLogs(selectedUserId, { page: logPage, page_size: PAGE_SIZE });
  const detailQuery = useClientLogBatch(selectedBatchId);

  React.useEffect(() => {
    if (!selectedUserId) {
      setSelectedUser(null);
      return;
    }
    const match = users.find((user) => user.id === selectedUserId);
    if (match) {
      setSelectedUser(match);
    }
  }, [selectedUserId, users]);

  const handleUserSelect = (user: User) => {
    setSelectedUser(user);
    setSelectedUserId(user.id);
    setLogPage(1);
    setSelectedBatchId(null);
    const params = new URLSearchParams();
    params.set('userId', user.id);
    setSearchParams(params);
  };

  const clearSelection = () => {
    setSelectedUser(null);
    setSelectedUserId('');
    setLogPage(1);
    setSelectedBatchId(null);
    setSearchParams(new URLSearchParams());
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Desktop Client Logs</h1>
        <p className="mt-1 text-sm text-slate-400">
          Select a user, then review synced desktop log batches uploaded from the Camxora desktop app.
        </p>
      </div>

      <div className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">Users</h2>
          <p className="mt-1 text-sm text-slate-400">
            Click a user row to load that account&apos;s desktop sync logs.
          </p>
        </div>
        {usersQuery.isError ? (
          <ErrorState
            message={(usersQuery.error as Error)?.message ?? 'Failed to load users'}
            onRetry={() => usersQuery.refetch()}
          />
        ) : (
          <DataTable<User>
            columns={userColumns}
            data={visibleUsers}
            totalCount={usersQuery.data?.total ?? 0}
            page={userPage}
            pageSize={USER_PAGE_SIZE}
            onPageChange={setUserPage}
            isLoading={usersQuery.isLoading}
            onRowClick={handleUserSelect}
            emptyMessage="No users found for the current page."
            filterBar={
              <FilterBar>
                <div className="min-w-[320px] flex-1">
                  <label className="mb-1 block text-xs uppercase tracking-wide text-slate-500">
                    Quick Filter
                  </label>
                  <Input
                    value={userSearch}
                    onChange={(e) => setUserSearch(e.target.value)}
                    placeholder="Search current page by email, name, or user ID"
                    className="bg-slate-900"
                  />
                </div>
              </FilterBar>
            }
          />
        )}
      </div>

      <div className="space-y-4 rounded-lg border border-slate-800 bg-slate-950/60 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-[320px] flex-1">
            <label className="mb-1 block text-xs uppercase tracking-wide text-slate-500">
              Selected User ID
            </label>
            <Input
              value={selectedUserId}
              readOnly
              placeholder="No user selected"
              className="bg-slate-900 font-mono text-xs text-slate-200"
            />
          </div>
          <Button variant="outline" onClick={clearSelection} disabled={!selectedUserId}>
            Clear selection
          </Button>
        </div>
        {selectedUserId ? (
          <div className="grid gap-2 text-sm text-slate-300">
            <div className="font-medium text-slate-100">
              {selectedUser?.display_name || 'Selected user'}
            </div>
            <div>{selectedUser?.email || 'Email not loaded on this page yet'}</div>
            <div className="font-mono text-xs text-slate-500">{selectedUserId}</div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">Choose a user from the table above to inspect desktop sync logs.</p>
        )}
      </div>

      {selectedUserId ? (
        listQuery.isError ? (
          <ErrorState
            message={(listQuery.error as Error)?.message ?? 'Failed to load client logs'}
            onRetry={() => listQuery.refetch()}
          />
        ) : (
          <div className="space-y-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Synced Log Batches</h2>
              <p className="mt-1 text-sm text-slate-400">
                Click a batch row to open the uploaded log content.
              </p>
            </div>
            <DataTable<ClientLogBatchSummary>
              columns={columns}
              data={listQuery.data?.items ?? []}
              totalCount={listQuery.data?.total ?? 0}
              page={logPage}
              pageSize={PAGE_SIZE}
              onPageChange={setLogPage}
              isLoading={listQuery.isLoading}
              onRowClick={(row) => setSelectedBatchId(row.id)}
              emptyMessage="No synced desktop logs for this user yet."
            />
          </div>
        )
      ) : null}

      {selectedBatchId ? (
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-100">Batch detail</h2>
            <Button variant="outline" onClick={() => setSelectedBatchId(null)}>
              Close
            </Button>
          </div>
          {detailQuery.isLoading ? (
            <p className="text-sm text-slate-400">Loading…</p>
          ) : detailQuery.isError ? (
            <p className="text-sm text-red-400">
              {(detailQuery.error as Error)?.message || 'Failed to load batch.'}
            </p>
          ) : (
            <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded bg-black/40 p-3 font-mono text-xs text-slate-200">
              {detailQuery.data?.content || 'Empty batch'}
            </pre>
          )}
        </div>
      ) : null}
    </div>
  );
}
