import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Icon } from "../../../components/icon";
import { Button } from "../../../components/button";
import { Card } from "../../../components/card";
import { Dialog, DialogClose, DialogContent } from "../../../components/dialog";
import { PageHeader } from "../../../components/page-header";
import { Badge, StatusDot } from "../../../components/status";
import { toast } from "../../../components/toast";
import { classNames, formatCount } from "../../../lib/format";
import { errorMessage } from "../../../lib/api";
import { MarketplaceCard, MarketplacePreview } from "../marketplace-card";
import {
  catalogSchema,
  formatPrice,
  kindLabel,
  licenseLabel,
  normalizeSearch,
  schemaLabel,
  schemaPolicy,
  supportsPipeline,
  totalPages,
} from "../marketplace-model";
import type { MarketplaceItem, MarketplaceKind } from "../marketplace-types";
import { useInstalledTemplates, useMarketplaceCatalog } from "../use-marketplace";

const LOAD_ERROR = "Unable to load the Marketplace right now.";
const KINDS: Array<{ key: MarketplaceKind; label: string }> = [
  { key: "all", label: "All" },
  { key: "video", label: "Video" },
  { key: "reel", label: "Reel" },
];

function SkeletonCard() {
  return (
    <Card className="overflow-hidden">
      <div className="aspect-video w-full animate-pulse bg-surface-2" />
      <div className="space-y-2 p-3">
        <div className="h-4 w-3/4 animate-pulse rounded bg-surface-2" />
        <div className="h-3 w-1/2 animate-pulse rounded bg-surface-2" />
        <div className="h-3 w-full animate-pulse rounded bg-surface-2" />
        <div className="h-8 w-24 animate-pulse rounded-control bg-surface-2" />
      </div>
    </Card>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2 last:border-b-0">
      <dt className="text-caption text-text-muted">{label}</dt>
      <dd className="truncate text-meta text-text-primary" title={value}>
        {value}
      </dd>
    </div>
  );
}

export function MarketplacePage() {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<MarketplaceKind>("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [installError, setInstallError] = useState<{ itemId: string; message: string } | null>(null);
  const [detailItem, setDetailItem] = useState<MarketplaceItem | null>(null);
  const [reinstallItem, setReinstallItem] = useState<MarketplaceItem | null>(null);

  // Search is debounced 300 ms and always resets to page 1.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(normalizeSearch(searchInput));
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const catalog = useMarketplaceCatalog(page, kind, search);
  const installed = useInstalledTemplates();

  // The shell is notified after an install; refresh the local pickers too.
  useEffect(() => {
    return window.camxora.templates.onChange(() => {
      void queryClient.invalidateQueries({ queryKey: ["templates"] });
      void queryClient.invalidateQueries({ queryKey: ["marketplace-catalog"] });
    });
  }, [queryClient]);

  const installedIds = useMemo(() => {
    const ids = new Set<string>();
    for (const template of installed.data ?? []) {
      if (template.marketplaceItemId) ids.add(template.marketplaceItemId);
    }
    return ids;
  }, [installed.data]);

  const items = catalog.data?.items ?? [];
  const total = catalog.data?.total ?? 0;
  const size = catalog.data?.page_size ?? 20;
  const pages = totalPages(total, size);
  const loading = catalog.isLoading && !catalog.data;
  const stale = catalog.isError && Boolean(catalog.data);
  const failed = catalog.isError && !catalog.data;
  const filtered = kind !== "all" || Boolean(search);

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["templates"] }),
      queryClient.invalidateQueries({ queryKey: ["marketplace-catalog"] }),
    ]);
  };

  const install = async (item: MarketplaceItem, reinstall: boolean) => {
    if (installingId) return;
    setInstallingId(item.id);
    setInstallError(null);
    try {
      const result = await window.camxora.templates.install({
        itemId: item.id,
        name: item.name,
        kind: item.kind,
        previewUrl: item.preview_url,
        reinstall,
      });
      if (!result.ok) {
        setInstallError({ itemId: item.id, message: result.error.message });
        toast(result.error.message, "danger");
        return;
      }
      toast(result.data.reinstalled ? "Template reinstalled" : "Template installed", "success");
      await invalidate();
    } catch (error) {
      const message = errorMessage(error);
      setInstallError({ itemId: item.id, message });
      toast(message, "danger");
    } finally {
      setInstallingId(null);
    }
  };

  const requestInstall = (item: MarketplaceItem) => {
    if (installingId) return;
    if (!supportsPipeline(catalogSchema(item))) {
      toast(schemaPolicy(catalogSchema(item)) ?? "This template is not supported.", "warning");
      return;
    }
    if (installedIds.has(item.id)) {
      setReinstallItem(item);
      return;
    }
    void install(item, false);
  };

  return (
    <div className="pb-6" data-testid="marketplace-workspace">
      <PageHeader
        eyebrow="Workspace"
        title="Marketplace"
        description="Browse Vizzy templates, inspect the preview and install one without restarting the app."
        actions={
          <>
            {stale ? <Badge tone="warning">Stale</Badge> : null}
            <span className="text-caption text-text-muted" data-testid="marketplace-total">
              {loading ? "" : `${formatCount(total)} template${total === 1 ? "" : "s"}`}
            </span>
            <Button
              variant="secondary"
              onClick={() => void catalog.refetch()}
              disabled={catalog.isFetching}
            >
              <Icon name="fa-rotate-right" size={14} className={catalog.isFetching ? "animate-spin" : undefined} />
              Refresh
            </Button>
          </>
        }
      />

      <div className="space-y-4 p-6">
        <div className="flex flex-wrap items-center gap-3">
          <div role="group" aria-label="Template kind" className="flex items-center gap-1 border-b border-border">
            {KINDS.map((entry) => (
              <button
                key={entry.key}
                aria-pressed={kind === entry.key}
                data-testid={`marketplace-kind-${entry.key}`}
                onClick={() => {
                  setKind(entry.key);
                  setPage(1);
                }}
                className={classNames(
                  "-mb-px border-b-2 px-3 pb-1.5 pt-1 text-body transition-colors",
                  kind === entry.key
                    ? "border-accent text-text-primary"
                    : "border-transparent text-text-secondary hover:text-text-primary",
                )}
              >
                {entry.label}
              </button>
            ))}
          </div>

          <div className="relative ml-auto w-[280px] max-w-full">
            <Icon
              name="fa-magnifying-glass"
              size={14}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search templates"
              aria-label="Search templates"
              data-testid="marketplace-search"
              className="h-8 w-full rounded-control border border-border bg-surface-1 pl-8 pr-3 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
            />
          </div>
          <Button
            variant="ghost"
            onClick={() => {
              setSearchInput("");
              setKind("all");
              setPage(1);
            }}
            disabled={!filtered && !searchInput}
          >
            Clear filters
          </Button>
        </div>

        {failed || installError ? (
          <Card className="border-danger/30 bg-danger-soft px-4 py-3" role="alert">
            <div className="flex items-start justify-between gap-4">
              <div>
                {failed ? (
                  <>
                    <p className="text-body font-medium text-danger">{LOAD_ERROR}</p>
                    <p className="mt-1 text-meta text-text-secondary">
                      {errorMessage(catalog.error)}
                    </p>
                  </>
                ) : null}
                {installError ? (
                  <p className={failed ? "mt-2 text-body text-danger" : "text-body text-danger"}>
                    {installError.message}
                  </p>
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {failed ? (
                  <Button variant="secondary" onClick={() => void catalog.refetch()}>
                    Retry
                  </Button>
                ) : null}
                {installError ? (
                  <Button variant="ghost" onClick={() => setInstallError(null)}>
                    Dismiss
                  </Button>
                ) : null}
              </div>
            </div>
          </Card>
        ) : null}

        {loading ? (
          <div
            className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
            data-testid="marketplace-skeleton"
          >
            {Array.from({ length: 8 }, (_, index) => (
              <SkeletonCard key={index} />
            ))}
          </div>
        ) : items.length === 0 && !failed ? (
          <Card className="p-6">
            <p className="text-body text-text-secondary" data-testid="marketplace-empty">
              No templates match this filter.
            </p>
            <Button
              className="mt-3"
              variant="secondary"
              onClick={() => {
                setSearchInput("");
                setKind("all");
                setPage(1);
              }}
            >
              Clear filters
            </Button>
          </Card>
        ) : (
          <>
            <div
              className={classNames(
                "grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4",
                catalog.isFetching ? "opacity-70" : undefined,
              )}
              data-testid="marketplace-grid"
            >
              {items.map((item) => (
                <MarketplaceCard
                  key={item.id}
                  item={item}
                  installed={installedIds.has(item.id)}
                  installing={installingId === item.id}
                  disabled={Boolean(installingId)}
                  onInstall={() => requestInstall(item)}
                  onOpen={() => setDetailItem(item)}
                />
              ))}
            </div>

            <div className="flex items-center justify-end gap-3">
              {catalog.isFetching ? <StatusDot tone="accent" label="Refreshing…" /> : null}
              <Button
                variant="secondary"
                disabled={page <= 1 || catalog.isFetching}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                data-testid="marketplace-prev"
              >
                Previous
              </Button>
              <span className="text-meta text-text-secondary" data-testid="marketplace-page-label">
                Page {page} of {pages}
              </span>
              <Button
                variant="secondary"
                disabled={page >= pages || catalog.isFetching}
                onClick={() => setPage((current) => Math.min(pages, current + 1))}
                data-testid="marketplace-next"
              >
                Next
              </Button>
            </div>
          </>
        )}
      </div>

      <Dialog open={Boolean(detailItem)} onOpenChange={(open) => !open && setDetailItem(null)}>
        {detailItem ? (
          <DialogContent
            title={detailItem.name}
            description={`${detailItem.author || "Unknown author"} · ${kindLabel(detailItem.kind)}`}
            className="max-w-2xl"
          >
            <MarketplacePreview item={detailItem} className="aspect-video w-full rounded-control" large />
            <dl className="mt-4">
              <MetaRow label="Kind" value={kindLabel(detailItem.kind)} />
              <MetaRow label="Schema" value={schemaLabel(catalogSchema(detailItem))} />
              <MetaRow label="Version" value={detailItem.version || "Not listed"} />
              <MetaRow label="Licence" value={licenseLabel(detailItem)} />
              <MetaRow label="Price" value={formatPrice(detailItem.price)} />
              <MetaRow label="Tags" value={detailItem.tags?.join(", ") || "None"} />
              <MetaRow label="Item ID" value={detailItem.id} />
            </dl>
            {schemaPolicy(catalogSchema(detailItem)) ? (
              <p className="mt-3 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-meta text-danger">
                {schemaPolicy(catalogSchema(detailItem))}
              </p>
            ) : null}
            <p className="mt-3 text-caption text-text-muted">
              {installedIds.has(detailItem.id)
                ? "Installed locally. Reinstalling keeps the same template identity."
                : "Installation downloads the bundle, validates template.json and manifest.json, then stores it locally. Installs are short and cannot be cancelled once the download starts."}
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <DialogClose asChild>
                <Button variant="secondary">Close</Button>
              </DialogClose>
              <Button
                variant="primary"
                loading={installingId === detailItem.id}
                disabled={
                  Boolean(installingId) || !supportsPipeline(catalogSchema(detailItem))
                }
                onClick={() => requestInstall(detailItem)}
              >
                {!supportsPipeline(catalogSchema(detailItem))
                  ? "Not supported"
                  : installedIds.has(detailItem.id)
                    ? "Reinstall"
                    : "Install"}
              </Button>
            </div>
          </DialogContent>
        ) : null}
      </Dialog>

      <Dialog
        open={Boolean(reinstallItem)}
        onOpenChange={(open) => !open && setReinstallItem(null)}
      >
        <DialogContent
          title="Template already installed"
          description="This template is already installed. Do you want to reinstall it?"
        >
          <p className="text-body text-text-secondary">
            Reinstalling replaces the stored files and keeps the same local template identity. No
            duplicate record is created.
          </p>
          <div className="mt-5 flex justify-end gap-2">
            <DialogClose asChild>
              <Button variant="secondary">Cancel</Button>
            </DialogClose>
            <Button
              variant="primary"
              loading={Boolean(installingId)}
              onClick={() => {
                const item = reinstallItem;
                setReinstallItem(null);
                if (item) void install(item, true);
              }}
            >
              Reinstall
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
