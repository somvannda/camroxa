import { create } from "zustand";

type ToastTone = "info" | "success" | "warning" | "danger";

export interface ToastItem {
  id: string;
  message: string;
  tone: ToastTone;
}

export interface ToastRecord extends ToastItem {
  at: number;
}

interface ToastState {
  items: ToastItem[];
  history: ToastRecord[];
  unread: number;
  panelOpen: boolean;
  setPanelOpen: (open: boolean) => void;
  push: (message: string, tone?: ToastTone, durationMs?: number) => string;
  dismiss: (id: string) => void;
  markAllRead: () => void;
  clearHistory: () => void;
}

const HISTORY_LIMIT = 40;

export const useToastStore = create<ToastState>((set, get) => ({
  items: [],
  history: [],
  unread: 0,
  panelOpen: false,
  setPanelOpen: (open) => set({ panelOpen: open }),
  push: (message, tone = "info", durationMs = 4000) => {
    const id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
    const record: ToastRecord = { id, message, tone, at: Date.now() };
    set({
      items: [...get().items, { id, message, tone }],
      history: [record, ...get().history].slice(0, HISTORY_LIMIT),
      unread: get().unread + 1,
    });
    if (durationMs > 0) {
      setTimeout(() => get().dismiss(id), durationMs);
    }
    return id;
  },
  dismiss: (id) => set({ items: get().items.filter((item) => item.id !== id) }),
  markAllRead: () => set({ unread: 0 }),
  clearHistory: () => set({ history: [], unread: 0 }),
}));

export function toast(message: string, tone: ToastTone = "info", durationMs = 4000): string {
  return useToastStore.getState().push(message, tone, durationMs);
}

// Re-export the icon map so the viewport and the notifications panel share it.
export const TOAST_ICONS: Record<ToastTone, string> = {
  info: "fa-circle-info",
  success: "fa-circle-check",
  warning: "fa-triangle-exclamation",
  danger: "fa-triangle-exclamation",
};

export const TOAST_TEXT: Record<ToastTone, string> = {
  info: "text-info",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
};
