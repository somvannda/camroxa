import { Icon } from "./icon";
import { classNames } from "../lib/format";
import {
  TOAST_ICONS,
  TOAST_TEXT,
  toast,
  useToastStore,
  type ToastRecord,
} from "./toast-store";

export { toast, useToastStore };

const toneBorder: Record<ToastRecord["tone"], string> = {
  info: "border-info/40",
  success: "border-success/40",
  warning: "border-warning/40",
  danger: "border-danger/40",
};

function relativeTime(at: number): string {
  const seconds = Math.max(0, Math.round((Date.now() - at) / 1000));
  if (seconds < 45) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)}h ago`;
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(at);
}

/** Transient toasts: floating top-right, opaque so page text never bleeds through. */
export function ToastViewport() {
  const items = useToastStore((state) => state.items);
  const dismiss = useToastStore((state) => state.dismiss);
  const panelOpen = useToastStore((state) => state.panelOpen);

  // The notifications panel lists the same events; keep the viewport clear
  // while it is open so the two surfaces never overlap.
  if (panelOpen) return null;

  return (
    <div
      className="pointer-events-none fixed right-4 top-16 z-[70] flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2"
      aria-live="polite"
      data-testid="toast-viewport"
    >
      {items.map((item) => (
        <div
          key={item.id}
          className={classNames(
            "pointer-events-auto flex items-start gap-2.5 rounded-card border bg-surface-1 p-3 text-body shadow-[0_18px_48px_rgba(0,0,0,.45)]",
            toneBorder[item.tone],
          )}
        >
          <Icon
            name={TOAST_ICONS[item.tone]}
            size={15}
            className={classNames("mt-0.5 shrink-0", TOAST_TEXT[item.tone])}
          />
          <p className="min-w-0 flex-1 break-words text-text-primary">{item.message}</p>
          <button
            className="shrink-0 text-text-muted hover:text-text-primary"
            onClick={() => dismiss(item.id)}
            aria-label="Dismiss notification"
          >
            <Icon name="fa-xmark" size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}

export function ToastHistoryList({ limit = 20 }: { limit?: number }) {
  const history = useToastStore((state) => state.history);
  const rows = history.slice(0, limit);
  if (rows.length === 0) {
    return (
      <p className="px-3 py-6 text-center text-meta text-text-secondary">
        No notifications yet. Saves, generations and uploads will appear here.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-border">
      {rows.map((item) => (
        <li key={item.id} className="flex items-start gap-2.5 px-3 py-2.5">
          <Icon
            name={TOAST_ICONS[item.tone]}
            size={13}
            className={classNames("mt-0.5 shrink-0", TOAST_TEXT[item.tone])}
          />
          <div className="min-w-0 flex-1">
            <p className="break-words text-meta text-text-primary">{item.message}</p>
            <p className="mt-0.5 text-[11px] text-text-muted">{relativeTime(item.at)}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
