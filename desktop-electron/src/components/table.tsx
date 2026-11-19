import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { classNames } from "../lib/format";

export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-auto rounded-card border border-border">
      <table className={classNames("w-full border-collapse text-body", className)} {...props} />
    </div>
  );
}

export function THead({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={classNames("bg-surface-2", className)} {...props} />;
}

export function TBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={className} {...props} />;
}

export function TR({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={classNames("border-b border-border last:border-b-0 hover:bg-surface-hover", className)}
      {...props}
    />
  );
}

export function TH({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={classNames(
        "h-9 whitespace-nowrap px-3 text-left text-meta font-medium text-text-muted",
        className,
      )}
      {...props}
    />
  );
}

export function TD({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={classNames("h-9 whitespace-nowrap px-3 text-text-primary", className)}
      {...props}
    />
  );
}
