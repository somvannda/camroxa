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

export type CreatorFieldErrors = Record<string, string>;

export class CreatorApiError extends Error {
  readonly status: number;
  readonly fields: CreatorFieldErrors;

  constructor(message: string, status: number, fields: CreatorFieldErrors = {}) {
    super(message);
    this.name = "CreatorApiError";
    this.status = status;
    this.fields = fields;
  }
}

type ErrorPayload = {
  error?: {
    message?: string;
    details?: {
      fields?: Record<string, unknown>;
      field?: string;
    };
  };
  detail?: unknown;
  message?: string;
};

function collectFieldErrors(data: ErrorPayload): CreatorFieldErrors {
  const fields: CreatorFieldErrors = {};
  const push = (key: unknown, message: unknown) => {
    if (!key || !message) return;
    const normalized = String(key).trim();
    if (!normalized || fields[normalized]) return;
    fields[normalized] = String(message);
  };

  const details = data.error?.details;
  if (details?.fields && typeof details.fields === "object") {
    for (const [key, value] of Object.entries(details.fields)) push(key, value);
  }
  if (details?.field) push(details.field, data.error?.message || "Invalid value");

  if (Array.isArray(data.detail)) {
    for (const item of data.detail) {
      if (!item || typeof item !== "object") continue;
      const entry = item as { loc?: unknown; msg?: unknown };
      const loc = Array.isArray(entry.loc)
        ? entry.loc.filter((part) => part !== "body")
        : [];
      push(loc[loc.length - 1], entry.msg);
    }
  } else if (data.detail && typeof data.detail === "object") {
    const detail = data.detail as { fields?: Record<string, unknown>; field?: string; message?: string };
    if (detail.fields) {
      for (const [key, value] of Object.entries(detail.fields)) push(key, value);
    }
    if (detail.field) push(detail.field, detail.message || "Invalid value");
  }

  return fields;
}

async function readError(
  response: Response,
  fallback: string
): Promise<{ message: string; fields: CreatorFieldErrors }> {
  try {
    const data = (await response.json()) as ErrorPayload;
    const detailMessage =
      typeof data.detail === "string"
        ? data.detail
        : data.detail && typeof data.detail === "object" && "message" in data.detail
          ? String((data.detail as { message?: unknown }).message || "")
          : "";
    return {
      message: data.error?.message || detailMessage || data.message || fallback,
      fields: collectFieldErrors(data),
    };
  } catch {
    return { message: fallback, fields: {} };
  }
}

async function publicJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    const parsed = await readError(response, `Request failed (${response.status})`);
    throw new CreatorApiError(parsed.message, response.status, parsed.fields);
  }
  return (await response.json()) as T;
}

async function studioJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await musicAuthFetch(path, init);
  if (!response.ok) {
    const parsed = await readError(response, `Request failed (${response.status})`);
    throw new CreatorApiError(parsed.message, response.status, parsed.fields);
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

export type CreatorReleaseSummary = {
  id: string;
  title: string;
  album_slug?: string | null;
  genre?: string | null;
  genres: string[];
  cover_url?: string | null;
  track_count: number;
  release_type: "single" | "album";
  published_at?: string | null;
};

export async function fetchCreatorReleases(
  handle: string
): Promise<{ items: CreatorReleaseSummary[] }> {
  return publicJson<{ items: CreatorReleaseSummary[] }>(
    `/api/v3/creators/${encodeURIComponent(handle)}/releases`
  );
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

export async function uploadCreatorMedia(
  kind: "avatar" | "banner",
  file: File
): Promise<{ url: string; kind: string }> {
  const form = new FormData();
  form.append("file", file);
  const response = await musicAuthFetch(
    `/api/v3/creator/me/media?kind=${encodeURIComponent(kind)}`,
    { method: "POST", body: form }
  );
  if (!response.ok) {
    const parsed = await readError(response, `Upload failed (${response.status})`);
    throw new CreatorApiError(parsed.message, response.status, parsed.fields);
  }
  return (await response.json()) as { url: string; kind: string };
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

export type CreatorEligibilityItem = {
  track_id: string;
  creator_id: string;
  status: "not_eligible" | "eligible" | "pending_verification" | "earning" | "suspended";
  valid_streams: number;
  unique_listeners: number;
  threshold_streams: number;
  threshold_listeners: number;
  notified_half_at?: string | null;
  notified_eligible_at?: string | null;
  eligible_at?: string | null;
  earning_started_at?: string | null;
  title?: string;
  origin?: string;
  publish_status?: string;
};

export type CreatorEligibilityResponse = {
  items: CreatorEligibilityItem[];
  summary: {
    tracks: number;
    eligible: number;
    earning: number;
    valid_streams: number;
  };
};

export async function fetchEligibility(): Promise<CreatorEligibilityResponse> {
  return studioJson<CreatorEligibilityResponse>("/api/v3/creator/eligibility");
}

export async function refreshEligibility(): Promise<CreatorEligibilityResponse & { refreshed: number }> {
  return studioJson<CreatorEligibilityResponse & { refreshed: number }>(
    "/api/v3/creator/eligibility/refresh",
    { method: "POST" }
  );
}

export type CreatorKyc = {
  user_id: string;
  legal_name: string;
  status: "pending" | "verified" | "rejected" | "expired";
  reason?: string | null;
  submitted_at?: string | null;
  reviewed_at?: string | null;
};

export type CreatorPayoutAccount = {
  id: string;
  method: "aba" | "wing" | "khqr" | "bank" | "paypal" | "wise";
  account_name: string;
  account_last4: string;
  bank_code?: string | null;
  currency: string;
  status: "pending" | "verified" | "rejected" | "disabled";
};

export type CreatorPayout = {
  id: string;
  amount_micros: number;
  currency: string;
  method: string;
  status: "requested" | "approved" | "processing" | "paid" | "failed" | "cancelled";
  requested_at?: string | null;
  paid_at?: string | null;
  payment_ref?: string | null;
};

export type CreatorPayoutStatus = {
  kyc: CreatorKyc | null;
  account: CreatorPayoutAccount | null;
  balance: {
    available_micros: number;
    available_usd: number;
    pending_micros: number;
    paid_micros: number;
    min_payout_micros: number;
  };
  payouts: CreatorPayout[];
};

export async function fetchPayoutStatus(): Promise<CreatorPayoutStatus> {
  return studioJson<CreatorPayoutStatus>("/api/v3/creator/payouts");
}

export async function submitKyc(input: {
  legal_name: string;
  date_of_birth: string;
  country_code: string;
  id_type: "passport" | "national_id" | "drivers_license";
  id_last4: string;
  id_document_ref: string;
  selfie_ref?: string;
  tax_id?: string;
}): Promise<{ kyc: CreatorKyc }> {
  return studioJson<{ kyc: CreatorKyc }>("/api/v3/creator/kyc", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function savePayoutAccount(input: {
  method: "aba" | "wing" | "khqr" | "bank" | "paypal" | "wise";
  account_name: string;
  account_last4: string;
  bank_code?: string;
  currency: "USD" | "KHR";
}): Promise<{ account: CreatorPayoutAccount }> {
  return studioJson<{ account: CreatorPayoutAccount }>("/api/v3/creator/payout-account", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function requestPayout(): Promise<{ payout: CreatorPayout }> {
  return studioJson<{ payout: CreatorPayout }>("/api/v3/creator/payouts/request", {
    method: "POST",
  });
}
