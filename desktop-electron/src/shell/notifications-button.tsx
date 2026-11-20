import { useQuery } from "@tanstack/react-query";
import { Icon } from "../components/icon";
import { ToastHistoryList, useToastStore } from "../components/toast";
import type { UpdateCheckResult, UpdateOffer } from "../../electron/shared/types";

async function checkForUpdate(): Promise<UpdateCheckResult> {
  if (!window.camxora?.updates) return { currentVersion: "", offer: null };
  const result = await window.camxora.updates.check();
  return result.ok ? result.data : { currentVersion: "", offer: null };
}

async function openOffer(offer: UpdateOffer): Promise<void> {
  if (!window.camxora?.updates) return;
  await window.camxora.updates.open(offer);
}

export function NotificationsButton() {
  const open = useToastStore((state) => state.panelOpen);
  const setPanelOpen = useToastStore((state) => state.setPanelOpen);
  const history = useToastStore((state) => state.history);
  const unread = useToastStore((state) => state.unread);
  const markAllRead = useToastStore((state) => state.markAllRead);
  const clearHistory = useToastStore((state) => state.clearHistory);

  return (
    <div className="relative">
      <button
        type="button"
        className="relative flex h-7 w-8 items-center justify-center rounded-[6px] text-text-secondary hover:bg-surface-hover hover:text-text-primary"
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
        aria-expanded={open}
        data-testid="notifications-button"
        onClick={() => {
          setPanelOpen(!open);
          if (!open) markAllRead();
        }}
      >
        <Icon name="fa-bell" size={14} />
        {unread > 0 ? (
          <span className="absolute right-0.5 top-0.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-accent px-0.5 text-[9px] font-semibold leading-none text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setPanelOpen(false)} aria-hidden="true" />
          <div
            className="absolute right-0 top-9 z-50 w-[340px] overflow-hidden rounded-card border border-border bg-surface-1 shadow-[0_18px_48px_rgba(0,0,0,.5)]"
            role="dialog"
            aria-label="Notifications"
            data-testid="notifications-panel"
          >
            <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
              <p className="text-body font-medium text-text-primary">Notifications</p>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  className="rounded-control px-1.5 py-0.5 text-caption text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                  onClick={() => markAllRead()}
                >
                  Mark read
                </button>
                <button
                  type="button"
                  className="rounded-control px-1.5 py-0.5 text-caption text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                  onClick={() => clearHistory()}
                >
                  Clear
                </button>
              </div>
            </div>
            <div className="max-h-[360px] overflow-y-auto">
              <ToastHistoryList />
            </div>
            <p className="border-t border-border px-3 py-1.5 text-[11px] text-text-muted">
              {history.length === 0
                ? "Nothing to review"
                : `${history.length} recent event${history.length === 1 ? "" : "s"}`}
            </p>
          </div>
        </>
      ) : null}
    </div>
  );
}

export function UpdateButton() {
  const check = useQuery<UpdateCheckResult>({
    queryKey: ["update-check"],
    queryFn: checkForUpdate,
    retry: 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const offer = check.data?.offer ?? null;

  // Python-desktop parity: the control only exists when an update is waiting.
  if (!offer) return null;

  return (
    <button
      type="button"
      className="relative flex h-7 w-8 items-center justify-center rounded-[6px] text-accent hover:bg-surface-hover"
      aria-label={`Update ${offer.version} available`}
      title={`Camxora ${offer.version} is available`}
      data-testid="update-button"
      onClick={() => void openOffer(offer)}
    >
      <Icon name="fa-download" size={13} />
      <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
    </button>
  );
}
