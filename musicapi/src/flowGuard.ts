/**
 * Pure decision logic for the generation-flow guard.
 *
 * Kept separate from `server.ts` (and free of DB/config imports) so the verdict
 * table is unit-testable without a database. `server.ts` resolves the owner and
 * completion from the DB and hands them here.
 */

export type AssetOwner = "caller" | "other" | "none";

export type AssetCheck = "ok" | "foreign" | "unowned" | "incomplete";

export interface FlowVerdictInput {
  /** Whether the flow guard is enabled at all (`config.flowGuard.enforced`). */
  enforced: boolean;
  /** Who `asset_owners` says owns the asset. */
  owner: AssetOwner;
  /** Defaults to true: a derivative requires a completed producer. */
  mustBeComplete?: boolean;
  /** Whether the job that produced the asset completed. Only meaningful for `caller`. */
  producedByCompletedJob?: boolean;
}

/**
 * Decide whether a derivative endpoint may consume an asset.
 *
 * - guard disabled → `"ok"` (inert rollout)
 * - another user's asset → `"foreign"`
 * - nobody's asset (unknown/never generated) → `"unowned"`
 * - caller's asset whose producer has not completed → `"incomplete"`
 * - otherwise → `"ok"`
 */
export function flowVerdict(input: FlowVerdictInput): AssetCheck {
  if (!input.enforced) return "ok";
  if (input.owner === "other") return "foreign";
  if (input.owner === "none") return "unowned";
  // owner === "caller" — the completion check applies only to the caller's asset.
  if (input.mustBeComplete !== false && input.producedByCompletedJob === false) {
    return "incomplete";
  }
  return "ok";
}
