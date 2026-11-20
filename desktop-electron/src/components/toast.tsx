import { useLocation } from "react-router-dom";
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
  const { pathname } = useLocation();
  // The Vizzy editor is a native view that paints above DOM. Only the 48 px
  // shell strip is visible, so a toast must stay inside it or it is cut off.
  const embedded = pathname.startsWith("/vizzy");
  const visible = embedded ? items.slice(0, 1) : items;

  // The notifications panel lists the same events; keep the viewport clear
  // while it is open so the two surfaces never overlap.
  if (panelOpen) return null;

  return (
    <div
      className={classNames(
        "pointer-events-none fixed z-[70] flex flex-col gap-2",
        embedded
          ? "left-1/2 top-1.5 w-auto max-w-[min(520px,calc(100vw-2rem))] -translate-x-1/2"
          : "right-4 top-16 w-[360px] max-w-[calc(100vw-2rem)]",
      )}
      aria-live="polite"
      data-testid="toast-viewport"
    >
      {visible.map((item) => (
        <div
          key={item.id}
          className={classNames(
            "pointer-events-auto flex items-start gap-2.5 rounded-card border bg-surface-1 shadow-[0_18px_48px_rgba(0,0,0,.45)]",
            embedded ? "px-2.5 py-1 text-caption" : "p-3 text-body",
            toneBorder[item.tone],
          )}
        >
          <Icon
            name={TOAST_ICONS[item.tone]}
            size={embedded ? 12 : 15}
            className={classNames("mt-0.5 shrink-0", TOAST_TEXT[item.tone])}
          />
          <p
            className={classNames(
              "min-w-0 flex-1 text-text-primary",
              embedded ? "truncate whitespace-nowrap" : "break-words",
            )}
          >
            {item.message}
          </p>
          <button
            className="shrink-0 text-text-muted hover:text-text-primary"
            onClick={() => dismiss(item.id)}
            aria-label="Dismiss notification"
          >
            <Icon name="fa-xmark" size={embedded ? 12 : 14} />
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
