import { Icon } from "../../components/icon";

export const DASHBOARD_ERROR_COPY =
  "Unable to load dashboard statistics right now. The shell still works, but dashboard data " +
  "needs the backend stats endpoint to respond successfully.";

export function DashboardErrorBanner({ message = DASHBOARD_ERROR_COPY }: { message?: string }) {
  return (
    <div
      className="flex items-start gap-3 rounded-card border border-danger/30 bg-danger-soft px-4 py-3"
      role="alert"
    >
      <Icon name="fa-triangle-exclamation" size={16} className="mt-0.5 shrink-0 text-danger" />
      <p className="text-body text-danger">{message}</p>
    </div>
  );
}
