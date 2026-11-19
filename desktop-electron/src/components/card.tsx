import type { HTMLAttributes } from "react";
import { classNames } from "../lib/format";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={classNames("card", className)} {...props} />;
}
