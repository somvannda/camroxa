import { Card } from "../../../components/card";
import { classNames } from "../../../lib/format";
import type { ChannelProfile } from "../music-types";

interface ChannelPairCardProps {
  side: "primary" | "secondary";
  title: string;
  profiles: ChannelProfile[];
  selectedIds: string[];
  onToggle: (profileId: string) => void;
  locked?: boolean;
  testId: string;
  note?: string;
}

export function ChannelPairCard({
  side,
  title,
  profiles,
  selectedIds,
  onToggle,
  locked = false,
  testId,
  note,
}: ChannelPairCardProps) {
  const order = new Map(selectedIds.map((id, index) => [id, index + 1]));

  return (
    <Card className="flex min-h-0 min-w-0 flex-col p-4" data-testid={testId}>
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-title font-semibold text-text-primary">{title}</h2>
        <span className="text-meta text-text-secondary text-tabular">
          {selectedIds.length} selected
        </span>
      </div>
      <p className="mt-1 text-meta text-text-secondary">
        {note ?? "Click to toggle. Pairing follows the order shown."}
      </p>

      <ul className="mt-3 min-h-0 flex-1 space-y-1 overflow-y-auto pr-1" aria-label={title}>
        {profiles.length === 0 ? (
          <li className="rounded-control border border-dashed border-border px-3 py-4 text-meta text-text-secondary">
            No profiles available yet.
          </li>
        ) : (
          profiles.map((profile) => {
            const index = order.get(profile.id);
            const selected = index !== undefined;
            return (
              <li key={profile.id}>
                <button
                  type="button"
                  className={classNames(
                    "flex h-8 w-full items-center gap-2 rounded-control border-l-2 px-2 text-left text-body transition-colors",
                    selected
                      ? "border-l-accent bg-accent-soft text-text-primary"
                      : "border-l-transparent text-text-secondary hover:bg-surface-hover hover:text-text-primary",
                    locked && "cursor-not-allowed opacity-60",
                  )}
                  aria-pressed={selected}
                  disabled={locked}
                  onClick={() => onToggle(profile.id)}
                  data-testid={`profile-toggle-${side}-${profile.id}`}
                >
                  <span
                    className={classNames(
                      "w-4 shrink-0 text-right font-mono text-caption text-tabular",
                      selected ? "text-accent" : "text-text-muted",
                    )}
                    aria-hidden="true"
                  >
                    {index ?? ""}
                  </span>
                  <span className="min-w-0 flex-1 truncate" title={profile.name}>
                    {profile.name}
                  </span>
                  {profile.run_prefix ? (
                    <span className="shrink-0 font-mono text-caption text-text-muted">
                      {profile.run_prefix}
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })
        )}
      </ul>
    </Card>
  );
}
