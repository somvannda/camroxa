import type { InputHTMLAttributes } from "react";
import { classNames } from "../lib/format";

export interface RangeProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  /** Optional numeric readout rendered on the right of the label. */
  readout?: string | number;
}

/** Shared range input with the accent track used by Music, Vizzy and Settings. */
export function Range({ className, readout, ...props }: RangeProps) {
  return (
    <div className={classNames("min-w-0", className)}>
      {readout !== undefined ? (
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-meta text-text-secondary text-tabular">{readout}</span>
        </div>
      ) : null}
      <input
        type="range"
        className="mt-1 w-full accent-accent disabled:opacity-40"
        {...props}
      />
    </div>
  );
}
