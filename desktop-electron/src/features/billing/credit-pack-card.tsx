import { Badge } from "../../components/status";
import { Button } from "../../components/button";
import { Card } from "../../components/card";
import { Icon } from "../../components/icon";
import { formatCount, formatCredits } from "../../lib/format";
import { extraValue, formatMoney, type CreditPack } from "./credit-pack";

export interface CreditPackCardProps {
  pack: CreditPack;
  /** The base pack used to calculate extra value. */
  base: CreditPack | undefined;
  popular: boolean;
  buying: boolean;
  disabled?: boolean;
  onBuy: (pack: CreditPack) => void;
  testIdPrefix: string;
}

/**
 * One production pricing card, shared by the Plan page and the in-app top-up
 * page so the packs read the same everywhere.
 */
export function CreditPackCard({
  pack,
  base,
  popular,
  buying,
  disabled = false,
  onBuy,
  testIdPrefix,
}: CreditPackCardProps) {
  const extra = extraValue(pack, base);
  return (
    <Card
      className={
        popular
          ? "relative flex flex-col border-accent-line p-4"
          : "flex flex-col p-4"
      }
      data-testid={`${testIdPrefix}-pack-${pack.slug}`}
    >
      {popular ? (
        <span className="absolute right-3 top-3">
          <Badge tone="accent">Most popular</Badge>
        </span>
      ) : null}
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-control bg-accent-soft text-accent">
          <Icon name={popular ? "fa-crown" : "fa-bolt"} size={12} />
        </span>
        <p className="text-body font-semibold text-text-primary">{pack.name}</p>
      </div>

      <div className="mt-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-[26px] font-semibold leading-8 text-text-primary text-tabular">
            {formatCredits(pack.total_credits)}
          </p>
          <p className="text-[10px] uppercase tracking-wide text-text-muted">Credits</p>
        </div>
        <div className="text-right">
          <p className="text-[20px] font-semibold leading-7 text-text-primary text-tabular">
            {formatMoney(pack.price_cents)}
          </p>
          <p className="text-[10px] uppercase tracking-wide text-text-muted">One-time</p>
        </div>
      </div>

      <dl className="mt-3 divide-y divide-border border-t border-border text-caption">
        <div className="flex items-center justify-between gap-2 py-1.5">
          <dt className="text-text-muted">Total songs</dt>
          <dd className="text-text-secondary text-tabular">
            {formatCount(pack.songs_equivalent)}
          </dd>
        </div>
        <div className="flex items-center justify-between gap-2 py-1.5">
          <dt className="text-text-muted">Extra value</dt>
          <dd
            className={
              extra === "Base"
                ? "text-text-secondary text-tabular"
                : "text-success text-tabular"
            }
          >
            {extra}
          </dd>
        </div>
        <div className="flex items-center justify-between gap-2 py-1.5">
          <dt className="text-text-muted">Valid</dt>
          <dd className="text-text-secondary">30 days</dd>
        </div>
        <div className="flex items-center justify-between gap-2 py-1.5">
          <dt className="text-text-muted">Delivery</dt>
          <dd className="text-success">Instant</dd>
        </div>
      </dl>

      <Button
        variant={popular ? "primary" : "secondary"}
        className="mt-4 w-full"
        loading={buying}
        disabled={disabled}
        onClick={() => onBuy(pack)}
        data-testid={`${testIdPrefix}-buy-${pack.slug}`}
      >
        {buying ? "Opening checkout…" : `Buy ${pack.name}`}
      </Button>
    </Card>
  );
}
