"use client";

import { platformJson } from "@/lib/auth-fetch";

export type NotificationItem = {
  id: string;
  event_type: string;
  category: string;
  title: string;
  message: string;
  delivered: boolean;
  created_at: string;
  expires_at: string | null;
  payload: Record<string, unknown>;
};

export type NotificationCenter = {
  items: NotificationItem[];
  unread_count: number;
  total: number;
};

export type MarkNotificationsReadResponse = {
  updated: number;
  unread_count: number;
};

export type SecuritySessionSummary = {
  client_id: string;
  source_ip: string;
  last_seen: string;
  successful_logins: number;
  failed_attempts: number;
  refresh_events: number;
  logout_events: number;
  last_outcome: string;
  activity_count: number;
};

export type SecurityEvent = {
  id: string;
  action_type: string;
  outcome: string;
  client_id: string;
  source_ip: string;
  endpoint_path: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
};

export type SecurityOverview = {
  sessions: SecuritySessionSummary[];
  events: SecurityEvent[];
  desktop_last_seen: string | null;
  web_last_seen: string | null;
};

export async function getNotificationCenter(): Promise<NotificationCenter> {
  return platformJson<NotificationCenter>({
    path: "/control-panel/notifications",
    method: "GET",
  });
}

export async function markNotificationsRead(input?: {
  ids?: string[];
  mark_all?: boolean;
}): Promise<MarkNotificationsReadResponse> {
  return platformJson<MarkNotificationsReadResponse>({
    path: "/control-panel/notifications/read",
    method: "POST",
    body: {
      ids: input?.ids ?? [],
      mark_all: input?.mark_all ?? false,
    },
  });
}

export async function getSecurityOverview(): Promise<SecurityOverview> {
  return platformJson<SecurityOverview>({
    path: "/control-panel/security-overview",
    method: "GET",
  });
}
