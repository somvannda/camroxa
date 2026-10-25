import { musicAuthFetch } from "@/lib/auth-fetch";

export type NotificationItem = {
  id: string;
  event_type: string;
  category: string;
  title: string;
  message: string;
  delivered: boolean;
  created_at: string;
  expires_at?: string | null;
  payload?: Record<string, unknown>;
};

export type NotificationCenter = {
  items: NotificationItem[];
  unread_count: number;
  total: number;
};

export async function fetchNotifications(): Promise<NotificationCenter> {
  const response = await musicAuthFetch("/api/v3/control-panel/notifications", {
    method: "GET",
  });
  if (!response.ok) {
    throw new Error(`Could not load notifications (${response.status})`);
  }
  return (await response.json()) as NotificationCenter;
}

export async function markNotificationsRead(markAll = true): Promise<void> {
  const response = await musicAuthFetch("/api/v3/control-panel/notifications/read", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mark_all: markAll }),
  });
  if (!response.ok) {
    throw new Error(`Could not update notifications (${response.status})`);
  }
}
