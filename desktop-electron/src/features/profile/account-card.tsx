import { Card } from "../../components/card";
import { Badge } from "../../components/status";
import type { UserMe } from "../dashboard/account-types";
import { accountInitials, accountName } from "./profile-format";

interface AccountCardProps {
  me: UserMe | null | undefined;
  loading: boolean;
  hasError: boolean;
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-caption text-text-muted">{label}</dt>
      <dd className={mono ? "mt-0.5 truncate font-mono text-meta text-text-primary" : "mt-0.5 truncate text-body text-text-primary"}>
        {value}
      </dd>
    </div>
  );
}

export function AccountCard({ me, loading, hasError }: AccountCardProps) {
  const verified = Boolean(me?.email_confirmed) && !hasError;
  const name = hasError ? "Loading account..." : loading ? "Loading account..." : accountName(me);
  const email = hasError
    ? "Unable to load account information."
    : loading
      ? "Loading account email..."
      : me?.email?.trim() || "--";
  const userId = hasError || loading ? "--" : me?.id || "--";
  const session = hasError ? "Needs attention" : "Active";

  return (
    <Card className="p-5" data-testid="profile-account">
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-title font-semibold text-text-primary">Account</h2>
        <Badge tone={verified ? "success" : "warning"}>{verified ? "Verified" : "Pending"}</Badge>
      </div>

      <div className="mt-4 flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-3 text-body font-semibold text-text-secondary">
          {hasError || loading ? "?" : accountInitials(me)}
        </div>
        <div className="min-w-0">
          <p className="truncate text-title font-medium text-text-primary">{name}</p>
          <p className="truncate text-body text-text-secondary">{email}</p>
        </div>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-border pt-4">
        <Field label="User ID" value={userId} mono />
        <Field label="Session" value={session} />
      </dl>
    </Card>
  );
}
