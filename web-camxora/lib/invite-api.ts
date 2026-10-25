import { musicAuthFetch } from "@/lib/auth-fetch";

export type InviteRewardRule = {
  mode: "percent" | "fixed";
  value: number;
};

export type InviteSettings = {
  enabled: boolean;
  inviter: InviteRewardRule;
  invitee: InviteRewardRule;
};

export type InviteRow = {
  id: string;
  invitee_email: string;
  status: "pending" | "rewarded" | "skipped" | "rejected";
  purchased_credits: number | null;
  reward: number;
  created_at: string | null;
  rewarded_at: string | null;
};

export type InviteProgram = {
  enabled: boolean;
  settings: InviteSettings;
  code: string;
  share_path: string;
  summary: {
    total: number;
    pending: number;
    rewarded: number;
    credits_earned: number;
  };
  invites: InviteRow[];
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      detail?: string | { message?: string };
      error?: { message?: string };
    };
    if (typeof data.detail === "string") return data.detail;
    if (data.detail && typeof data.detail === "object" && data.detail.message) {
      return data.detail.message;
    }
    if (data.error?.message) return data.error.message;
  } catch {
    /* ignore */
  }
  return fallback;
}

export async function fetchInviteProgram(): Promise<InviteProgram> {
  const response = await musicAuthFetch("/api/v3/web-music/invite", { method: "GET" });
  if (!response.ok) {
    throw new Error(await readError(response, `Could not load invites (${response.status})`));
  }
  return (await response.json()) as InviteProgram;
}
