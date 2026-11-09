import { musicAuthFetch } from "@/lib/auth-fetch";

export type CreatorStats = {
  followers: number;
  monthly_listeners: number;
  releases: number;
  valid_streams: number;
};

export type CreatorLink = { label: string; url: string };

export type CreatorProfile = {
  handle: string;
  display_name: string;
  tagline?: string | null;
  bio?: string | null;
  avatar_url?: string | null;
  banner_url?: string | null;
  country_code?: string | null;
  city?: string | null;
  genres: string[];
  influences: string[];
  links: CreatorLink[];
  ai_disclosure: "none" | "ai_assisted" | "ai_artist";
  tier: "creator" | "verified" | "partner";
  badges: string[];
  support_enabled: boolean;
  joined_at?: string | null;
  stats: CreatorStats;
  is_following: boolean;
};

export type CreatorStudioProfile = CreatorProfile & {
  user_id: string;
  payout_currency: string;
  status: string;
  pronouns?: string | null;
  program_joined_at?: string | null;
};

export type CreatorChecklist = Record<string, boolean>;

export type CreatorStudioResponse = {
  profile: CreatorStudioProfile | null;
  checklist: CreatorChecklist;
};

export type CreatorListResponse = {
  items: CreatorProfile[];
  total: number;
  limit: number;
  offset: number;
};

export class CreatorApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "CreatorApiError";
    this.status = status;
  }
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as {
      error?: { message?: string };
      detail?: string | { message?: string };
      message?: string;
    };
    return (
      data.error?.message ||
      (typeof data.detail === "string" ? data.detail : data.detail?.message) ||
      data.message ||
      fallback
    );
  } catch {
    return fallback;
  }
}

async function publicJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new CreatorApiError(await readError(response, `Request failed (${response.status})`), response.status);
  }
  return (await response.json()) as T;
}

async function studioJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await musicAuthFetch(path, init);
  if (!response.ok) {
    throw new CreatorApiError(await readError(response, `Request failed (${response.status})`), response.status);
  }
  return (await response.json()) as T;
}

export async function fetchCreators(params: {
  q?: string;
  genre?: string;
  country?: string;
  verifiedOnly?: boolean;
  sort?: "followers" | "newest" | "name";
  limit?: number;
  offset?: number;
} = {}): Promise<CreatorListResponse> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.genre) query.set("genre", params.genre);
  if (params.country) query.set("country", params.country);
  if (params.verifiedOnly) query.set("verified_only", "true");
  if (params.sort) query.set("sort", params.sort);
  query.set("limit", String(params.limit ?? 24));
  query.set("offset", String(params.offset ?? 0));
  return publicJson<CreatorListResponse>(`/api/v3/creators?${query.toString()}`);
}

export async function fetchCreator(handle: string): Promise<CreatorProfile> {
  return publicJson<CreatorProfile>(`/api/v3/creators/${encodeURIComponent(handle)}`);
}

export async function fetchMyCreator(): Promise<CreatorStudioResponse> {
  return studioJson<CreatorStudioResponse>("/api/v3/creator/me");
}

export async function checkHandle(handle: string): Promise<{
  handle: string;
  available: boolean;
  reason: string | null;
  suggestions: string[];
}> {
  return studioJson(`/api/v3/creator/handle-available?handle=${encodeURIComponent(handle)}`);
}

export type CreatorInput = {
  handle?: string;
  display_name?: string;
  tagline?: string;
  bio?: string;
  country_code?: string;
  city?: string;
  avatar_url?: string;
  banner_url?: string;
  genres?: string[];
  influences?: string[];
  ai_disclosure?: "none" | "ai_assisted" | "ai_artist";
  support_enabled?: boolean;
};

export async function claimCreator(input: CreatorInput): Promise<CreatorStudioResponse> {
  return studioJson<CreatorStudioResponse>("/api/v3/creator/claim", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function updateCreator(input: CreatorInput): Promise<CreatorStudioResponse> {
  return studioJson<CreatorStudioResponse>("/api/v3/creator/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export type CreatorApplication = {
  id: string;
  status: "draft" | "submitted" | "in_review" | "changes_requested" | "approved" | "rejected" | "withdrawn";
  version: number;
  requested_tier: string;
  payload: Record<string, unknown>;
  submitted_at?: string | null;
  sla_due_at?: string | null;
  reviewed_at?: string | null;
  decision_reason?: string | null;
};

export type CreatorVerification = {
  id: string;
  kind: "identity" | "authenticity" | "business" | "voice_consent";
  status: "pending" | "approved" | "rejected" | "expired";
  evidence_ref?: string | null;
  reason?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
};

export type CreatorBadge = {
  id: string;
  badge: string;
  granted_at?: string | null;
  expires_at?: string | null;
  revoked_at?: string | null;
  reason?: string | null;
};

export type CreatorProgramStatus = {
  profile: { handle: string; tier: string; status: string } | null;
  application: CreatorApplication | null;
  verifications: CreatorVerification[];
  badges: CreatorBadge[];
};

export async function fetchProgramStatus(): Promise<CreatorProgramStatus> {
  return studioJson<CreatorProgramStatus>("/api/v3/creator/application");
}

export async function submitApplication(input: {
  pitch: string;
  links: CreatorLink[];
  track_ids?: string[];
  rights_attested: boolean;
  requested_tier?: "verified";
  identity?: Record<string, unknown>;
}): Promise<{ application: CreatorApplication }> {
  return studioJson<{ application: CreatorApplication }>("/api/v3/creator/application", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function withdrawApplication(): Promise<{ application: CreatorApplication }> {
  return studioJson<{ application: CreatorApplication }>("/api/v3/creator/application/withdraw", {
    method: "POST",
  });
}

export async function submitVerification(input: {
  kind: CreatorVerification["kind"];
  evidence_ref: string;
}): Promise<{ verification: CreatorVerification }> {
  return studioJson<{ verification: CreatorVerification }>("/api/v3/creator/verification", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export type CreatorRelease = {
  id: string;
  creator_id: string;
  source_type: string;
  source_task_id: string;
  source_variant: "ok" | "alt";
  album_id?: string | null;
  track_id?: string | null;
  status:
    | "draft"
    | "submitted"
    | "in_review"
    | "changes_requested"
    | "approved"
    | "scheduled"
    | "published"
    | "taken_down"
    | "rejected";
  metadata: {
    title?: string;
    genre?: string;
    genres?: string[];
    language?: string;
    release_type?: string;
    rights_attested?: boolean;
    lyrics?: string | null;
    description?: string | null;
    cover_url?: string | null;
    release_date?: string | null;
  };
  ai_disclosure: string;
  origin: string;
  submitted_at?: string | null;
  sla_due_at?: string | null;
  reviewed_at?: string | null;
  published_at?: string | null;
  takedown_reason?: string | null;
  created_at?: string | null;
};

export async function fetchReleases(): Promise<{ items: CreatorRelease[] }> {
  return studioJson<{ items: CreatorRelease[] }>("/api/v3/creator/releases");
}

export async function createRelease(input: {
  source_task_id: string;
  variant: "ok" | "alt";
  metadata: CreatorRelease["metadata"];
}): Promise<{ release: CreatorRelease }> {
  return studioJson<{ release: CreatorRelease }>("/api/v3/creator/releases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function submitRelease(releaseId: string): Promise<{ release: CreatorRelease }> {
  return studioJson<{ release: CreatorRelease }>(
    `/api/v3/creator/releases/${encodeURIComponent(releaseId)}/submit`,
    { method: "POST" }
  );
}

export async function withdrawRelease(releaseId: string): Promise<{ release: CreatorRelease }> {
  return studioJson<{ release: CreatorRelease }>(
    `/api/v3/creator/releases/${encodeURIComponent(releaseId)}/withdraw`,
    { method: "POST" }
  );
}

export async function unpublishRelease(releaseId: string): Promise<{ release: CreatorRelease }> {
  return studioJson<{ release: CreatorRelease }>(
    `/api/v3/creator/releases/${encodeURIComponent(releaseId)}/unpublish`,
    { method: "POST" }
  );
}
