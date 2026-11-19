import { create } from "zustand";
import { Icon } from "./icon";
import { classNames } from "../lib/format";

type ToastTone = "info" | "success" | "warning" | "danger";

interface ToastItem {
  id: string;
  message: string;
  tone: ToastTone;
}

interface ToastState {
  items: ToastItem[];
  push: (message: string, tone?: ToastTone, durationMs?: number) => string;
  dismiss: (id: string) => void;
}

export const useToastStore = create<ToastState>((set, get) => ({
  items: [],
  push: (message, tone = "info", durationMs = 4000) => {
    const id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
    set({ items: [...get().items, { id, message, tone }] });
    if (durationMs > 0) {
      setTimeout(() => get().dismiss(id), durationMs);
    }
    return id;
  },
  dismiss: (id) => set({ items: get().items.filter((item) => item.id !== id) }),
}));

const toneClass: Record<ToastTone, string> = {
  info: "border-info/30 bg-info-soft text-info",
  success: "border-success/30 bg-success-soft text-success",
  warning: "border-warning/30 bg-warning-soft text-warning",
  danger: "border-danger/30 bg-danger-soft text-danger",
};

const toneIcon: Record<ToastTone, string> = {
  info: "fa-circle-info",
  success: "fa-circle-check",
  warning: "fa-triangle-exclamation",
  danger: "fa-triangle-exclamation",
};

export function ToastViewport() {
  const items = useToastStore((state) => state.items);
  const dismiss = useToastStore((state) => state.dismiss);

  return (
    <div className="pointer-events-none fixed bottom-10 right-4 z-50 flex w-[320px] flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className={classNames(
            "pointer-events-auto flex items-start gap-2 rounded-control border p-3 text-body shadow-lg",
            toneClass[item.tone],
          )}
        >
          <Icon name={toneIcon[item.tone]} size={15} className="mt-0.5 shrink-0" />
          <p className="flex-1 text-text-primary">{item.message}</p>
          <button
            className="text-text-muted hover:text-text-primary"
            onClick={() => dismiss(item.id)}
            aria-label="Dismiss"
          >
            <Icon name="fa-xmark" size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}

export function toast(message: string, tone: ToastTone = "info", durationMs = 4000): string {
  return useToastStore.getState().push(message, tone, durationMs);
}
