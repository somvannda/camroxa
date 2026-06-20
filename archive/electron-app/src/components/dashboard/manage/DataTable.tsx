import * as React from "react";
import { cn } from "@/lib/utils";

export type TableColumn<T> = {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  span?: number;
};

export function DataTable<T extends { id: string }>(props: {
  columns: TableColumn<T>[];
  rows: T[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  maxHeightClassName?: string;
  fill?: boolean;
}) {
  const cols = React.useMemo(() => props.columns.map((c) => c.span ?? 1), [props.columns]);
  const gridTemplateColumns = React.useMemo(() => cols.map((n) => `${n}fr`).join(" "), [cols]);
  const bodyHeightClassName = props.fill ? "" : props.maxHeightClassName ?? "max-h-[600px]";

  return (
    <div className={cn("overflow-hidden rounded-lg border border-slate-200/10", props.fill ? "flex h-full flex-col" : "")}>
      <div
        className={cn("grid bg-slate-950/40 px-3 py-2 text-xs text-slate-300")}
        style={{ gridTemplateColumns }}
      >
        {props.columns.map((c) => (
          <div key={c.key} className="truncate">
            {c.header}
          </div>
        ))}
      </div>
      <div
        className={cn(
          "min-h-0 overflow-auto bg-[#0b142b]",
          props.fill ? "flex-1" : "",
          bodyHeightClassName,
        )}
      >
        {props.rows.length === 0 ? (
          <div className="px-3 py-10 text-center text-sm text-slate-400">No rows.</div>
        ) : (
          props.rows.map((row) => (
            <button
              key={row.id}
              type="button"
              onClick={() => props.onSelect(row.id)}
              className={cn(
                "grid w-full items-center border-t border-slate-200/10 px-3 py-2 text-left text-sm",
                props.selectedId === row.id ? "bg-blue-600/20" : "hover:bg-slate-800/40",
              )}
              style={{ gridTemplateColumns }}
            >
              {props.columns.map((c) => (
                <div key={c.key} className="truncate text-slate-100">
                  {c.render(row)}
                </div>
              ))}
            </button>
          ))
        )}
      </div>
    </div>
  );
}

