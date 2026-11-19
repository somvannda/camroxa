import { useEffect, useState } from "react";
import { Icon } from "../../components/icon";
import { Button } from "../../components/button";
import { classNames, formatCount } from "../../lib/format";
import {
  catalogSchema,
  formatPrice,
  installLabel,
  kindLabel,
  schemaLabel,
  schemaPolicy,
  supportsPipeline,
} from "./marketplace-model";
import { loadPreview } from "./marketplace-preview";
import type { MarketplaceItem } from "./marketplace-types";

type PreviewState =
  | { status: "loading" }
  | { status: "ready"; dataUrl: string }
  | { status: "error" };

export function useMarketplacePreview(item: MarketplaceItem): PreviewState {
  const [state, setState] = useState<PreviewState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    void loadPreview(item.id, item.preview_url)
      .then((dataUrl) => {
        if (!cancelled) setState({ status: "ready", dataUrl });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [item.id, item.preview_url]);

  return state;
}

export function MarketplacePreview({
  item,
  className,
  large = false,
}: {
  item: MarketplaceItem;
  className?: string;
  large?: boolean;
}) {
  const preview = useMarketplacePreview(item);
  return (
    <div
      className={classNames(
        "relative flex items-center justify-center overflow-hidden bg-surface-2",
        className,
      )}
    >
      {preview.status === "ready" ? (
        <img
          src={preview.dataUrl}
          alt={`${item.name} preview`}
          loading={large ? "eager" : "lazy"}
          className="h-full w-full object-cover"
        />
      ) : (
        <div className="flex flex-col items-center gap-1.5 text-text-muted">
          <Icon name="fa-image" size={large ? 22 : 18} />
          <span className="text-caption">
            {preview.status === "loading" ? "Loading preview…" : "No preview"}
          </span>
        </div>
      )}
    </div>
  );
}

export function MarketplaceCard({
  item,
  installed,
  installing,
  disabled,
  onInstall,
  onOpen,
}: {
  item: MarketplaceItem;
  installed: boolean;
  installing: boolean;
  disabled: boolean;
  onInstall: () => void;
  onOpen: () => void;
}) {
  const schema = catalogSchema(item);
  const supported = supportsPipeline(schema);
  const policy = schemaPolicy(schema);

  return (
    <article
      className="card flex flex-col overflow-hidden"
      data-testid={`marketplace-card-${item.id}`}
      data-installed={installed ? "true" : "false"}
    >
      <button
        type="button"
        onClick={onOpen}
        aria-label={`View ${item.name}`}
        className="block aspect-video w-full text-left"
      >
        <MarketplacePreview item={item} className="h-full w-full" />
      </button>

      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <button type="button" onClick={onOpen} className="min-w-0 text-left">
            <h2
              className="line-clamp-2 text-title font-semibold text-text-primary"
              title={item.name}
            >
              {item.name}
            </h2>
          </button>
          <span className="shrink-0 font-mono text-meta text-text-secondary">
            {formatPrice(item.price)}
          </span>
        </div>

        <p className="truncate text-meta text-text-secondary" title={item.author || undefined}>
          {item.author || "Unknown author"}
        </p>
        <p className="truncate text-caption text-text-muted" title={item.description || undefined}>
          {item.description || "No description provided."}
        </p>

        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-text-secondary">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-text-muted" />
            {kindLabel(item.kind)}
          </span>
          <span className="text-text-muted">·</span>
          <span className={supported ? "text-text-secondary" : "text-danger"}>
            {schemaLabel(schema)}
          </span>
          {item.version ? (
            <>
              <span className="text-text-muted">·</span>
              <span className="font-mono">v{item.version}</span>
            </>
          ) : null}
        </div>

        {policy ? (
          <p className="text-caption text-danger" data-testid={`marketplace-legacy-${item.id}`}>
            {policy}
          </p>
        ) : null}

        <div className="mt-auto flex items-center justify-between gap-2 pt-1">
          {installed ? (
            <span
              className="inline-flex items-center gap-1 text-caption text-success"
              data-testid={`marketplace-installed-${item.id}`}
            >
              <Icon name="fa-check" size={13} />
              Installed
            </span>
          ) : (
            <span className="text-caption text-text-muted">
              {formatCount(item.tags?.length ?? 0)}{" "}
              {(item.tags?.length ?? 0) === 1 ? "tag" : "tags"}
            </span>
          )}
          <Button
            variant={installed ? "secondary" : "primary"}
            data-testid={`marketplace-install-${item.id}`}
            loading={installing}
            disabled={disabled || !supported}
            title={policy ?? undefined}
            onClick={onInstall}
          >
            {installing ? null : installed ? <Icon name="fa-check" size={14} /> : <Icon name="fa-download" size={14} />}
            {!supported ? "Not supported" : installLabel(installed, installing)}
          </Button>
        </div>
      </div>
    </article>
  );
}
