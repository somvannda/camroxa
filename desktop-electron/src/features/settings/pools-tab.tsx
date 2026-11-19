import { Button } from "../../components/button";
import { Icon } from "../../components/icon";
import { Badge } from "../../components/status";
import { Table, TBody, TD, TH, THead, TR } from "../../components/table";
import { classNames } from "../../lib/format";
import {
  POOL_KINDS,
  POOL_PAGE_SIZE,
  canPoolNext,
  canPoolPrevious,
  poolPageLabel,
  poolRangeLabel,
  type PoolKind,
  type PoolStat,
} from "./settings-types";
import {
  EmptyState,
  ErrorBanner,
  Note,
  Section,
  Skeleton,
} from "./settings-fields";
import type { SettingsWorkspace } from "./use-settings-workspace";

function statValue(loading: boolean, unavailable: boolean, stat: PoolStat | null, field: "total" | "unused") {
  if (loading) return "—";
  if (unavailable || !stat) return "Unavailable";
  return String(stat[field]);
}

function StatCard({
  label,
  hint,
  value,
  tone = "neutral",
}: {
  label: string;
  hint: string;
  value: string;
  tone?: "neutral" | "accent";
}) {
  return (
    <div className="rounded-control border border-border bg-surface-1 p-3">
      <p className="text-meta text-text-secondary">{label}</p>
      <p
        className={classNames(
          "mt-1 text-title font-semibold text-tabular",
          tone === "accent" ? "text-accent" : "text-text-primary",
        )}
      >
        {value}
      </p>
      <p className="mt-1 text-caption text-text-muted">{hint}</p>
    </div>
  );
}

function poolKindHint(kind: PoolKind): string {
  if (kind === "openings") return "Two-line opening pairs used to start a track.";
  if (kind === "titles") return "Song titles handed out to new generations.";
  return "Album names shared by a batch of tracks.";
}

export function PoolsTab({ workspace }: { workspace: SettingsWorkspace }) {
  const ws = workspace;
  const statsLoading = ws.poolStatsLoading;
  const statsUnavailable = Boolean(ws.poolStatsError);
  const statOf = (kind: PoolKind): PoolStat | null => (ws.poolStats ? ws.poolStats[kind] : null);
  const total = ws.poolTotal;
  const kindLabel = POOL_KINDS.find((kind) => kind.id === ws.poolKind)?.label ?? ws.poolKind;

  return (
    <div className="space-y-4" data-testid="settings-pools-tab">
      {ws.poolStatsError ? (
        <ErrorBanner
          message={`Pool counts are unavailable right now. ${ws.poolStatsError}`}
          onRetry={ws.retryPools}
        />
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="settings-pools-stats">
        {POOL_KINDS.map((kind) => (
          <StatCard
            key={kind.id}
            label={kind.label}
            hint={`${statValue(statsLoading, statsUnavailable, statOf(kind.id), "unused")} unused`}
            value={statValue(statsLoading, statsUnavailable, statOf(kind.id), "total")}
            tone={ws.poolKind === kind.id ? "accent" : "neutral"}
          />
        ))}
        <StatCard
          label="Ownership"
          hint="Shared pools; editing stays in the Admin Portal"
          value="Account-wide"
        />
      </div>

      <Section
        title="Content pools"
        description="Read-only view of what the generators can draw from."
        action={
          <Button
            variant="secondary"
            className="h-8"
            loading={ws.poolItemsFetching || statsLoading}
            disabled={ws.poolItemsFetching || statsLoading}
            onClick={ws.refreshPools}
          >
            <Icon name="fa-rotate-right" size={13} />
            Refresh
          </Button>
        }
        data-testid="settings-pools-table-section"
      >
        <div className="flex flex-wrap gap-2" role="group" aria-label="Pool kind">
          {POOL_KINDS.map((kind) => {
            const active = ws.poolKind === kind.id;
            return (
              <button
                key={kind.id}
                type="button"
                aria-pressed={active}
                data-pool-kind={kind.id}
                className={classNames(
                  "h-8 rounded-control border px-3 text-body transition-colors",
                  active
                    ? "border-accent-line bg-accent-soft text-accent"
                    : "border-border bg-surface-1 text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                )}
                onClick={() => ws.selectPoolKind(kind.id)}
              >
                {kind.label}
              </button>
            );
          })}
        </div>
        <p className="text-caption text-text-muted">{poolKindHint(ws.poolKind)}</p>

        {ws.poolItemsError ? (
          <ErrorBanner
            message={`The ${kindLabel.toLowerCase()} pool could not be loaded. ${ws.poolItemsError}`}
            onRetry={ws.retryPools}
          />
        ) : ws.poolItemsLoading ? (
          <div data-testid="settings-pools-loading">
            <Skeleton rows={6} />
          </div>
        ) : ws.poolItems.length === 0 ? (
          <EmptyState
            message={
              ws.poolOffset > 0
                ? "This page is empty. Go back to the previous page."
                : `The ${kindLabel.toLowerCase()} pool has no entries yet.`
            }
          />
        ) : (
          <div className="max-h-[420px] overflow-auto" data-testid="settings-pools-table">
            <Table>
              <THead>
                <TR>
                  <TH className="w-16 text-right">ID</TH>
                  <TH>Entry</TH>
                  <TH className="w-20 text-right">Used</TH>
                  <TH className="w-28">Created</TH>
                </TR>
              </THead>
              <TBody>
                {ws.poolItems.map((item) => (
                  <TR key={item.id}>
                    <TD className="text-right text-tabular text-text-muted">{item.id}</TD>
                    <TD className="whitespace-normal">
                      <span className="block text-text-primary">{item.text || "—"}</span>
                      {item.secondaryText ? (
                        <span className="block text-caption text-text-muted">{item.secondaryText}</span>
                      ) : null}
                    </TD>
                    <TD className="text-right text-tabular">{item.usedCount}</TD>
                    <TD className="text-text-muted">
                      {item.createdAt && !Number.isNaN(new Date(item.createdAt).getTime())
                        ? new Date(item.createdAt).toLocaleDateString()
                        : "—"}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
          <span
            className="text-caption text-text-muted"
            data-testid="settings-pools-page-label"
          >
            {poolPageLabel(total, ws.poolOffset, POOL_PAGE_SIZE)} ·{" "}
            {poolRangeLabel(total, ws.poolOffset, POOL_PAGE_SIZE)}
          </span>
          <div className="flex items-center gap-2">
            <Badge tone="neutral">Page size {POOL_PAGE_SIZE}</Badge>
            <Button
              variant="secondary"
              className="h-8"
              disabled={!canPoolPrevious(ws.poolOffset) || ws.poolItemsFetching}
              onClick={ws.previousPoolPage}
              data-testid="settings-pools-prev"
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              className="h-8"
              disabled={!canPoolNext(total, ws.poolOffset, POOL_PAGE_SIZE) || ws.poolItemsFetching}
              onClick={ws.nextPoolPage}
              data-testid="settings-pools-next"
            >
              Next
            </Button>
          </div>
        </div>
      </Section>

      <Note>
        Content pools are read-only in the desktop app. Adding, importing, clearing and editing pool
        entries happens in the Admin Portal; changes appear here after Refresh.
      </Note>
    </div>
  );
}
