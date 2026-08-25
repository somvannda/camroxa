/**
 * Resolve API base URL for User Portal.
 * In production, prefer same-origin `/api/v3` so nginx can proxy to the platform API
 * and auth cookies stay first-party. Set NEXT_PUBLIC_PLATFORM_API_BASE_URL only when
 * the API is on a different host without a reverse-proxy `/api` route.
 */
export function resolvePlatformApiBaseUrl(): string {
  const configured = String(process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL ?? "").trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }
  if (process.env.NODE_ENV === "production") {
    return "/api/v3";
  }
  return "http://localhost:8000/api/v3";
}

export const PLATFORM_API_BASE_URL = resolvePlatformApiBaseUrl();

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};

export type RegisterResponse = {
  id: string;
  email: string;
  display_name: string;
};

export type SignupModeResponse = {
  mode: "open" | "invite_only";
};

export type ValidateInvitationResponse = {
  ok: boolean;
  code_hint?: string | null;
  label?: string | null;
};

type ErrorResponseShape = {
  detail?: string;
  error?: {
    message?: string;
    details?: {
      fields?: Array<{ field?: string; message?: string }>;
    };
  };
};

async function readErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as ErrorResponseShape;
    if (data?.detail) return data.detail;
    const fieldErrors = data?.error?.details?.fields
      ?.map((item) => item.message?.trim())
      .filter(Boolean);
    if (fieldErrors?.length) return fieldErrors.join(" ");
    if (data?.error?.message) return data.error.message;
  } catch {}
  return fallback;
}

export async function loginWithEmailPassword(input: {
  email: string;
  password: string;
}): Promise<TokenResponse> {
  const response = await fetch(`${PLATFORM_API_BASE_URL}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Portal-Context": "user",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Login failed (${response.status})`));
  }

  return (await response.json()) as TokenResponse;
}

export async function registerWithEmailPassword(input: {
  email: string;
  password: string;
  display_name: string;
  invitation_code?: string;
}): Promise<RegisterResponse> {
  const response = await fetch(`${PLATFORM_API_BASE_URL}/auth/register`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Portal-Context": "user",
      "X-Signup-Product": "studio",
    },
    body: JSON.stringify({ ...input, product: "studio" }),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Registration failed (${response.status})`));
  }

  return (await response.json()) as RegisterResponse;
}

export async function getSignupMode(): Promise<SignupModeResponse> {
  const response = await fetch(`${PLATFORM_API_BASE_URL}/auth/signup-mode`, {
    method: "GET",
    credentials: "include",
    headers: {
      "X-Portal-Context": "user",
    },
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Unable to load signup mode (${response.status})`));
  }

  return (await response.json()) as SignupModeResponse;
}

export async function validateInvitationCode(invitation_code: string): Promise<ValidateInvitationResponse> {
  const response = await fetch(`${PLATFORM_API_BASE_URL}/auth/validate-invitation`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Portal-Context": "user",
    },
    body: JSON.stringify({ invitation_code }),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Invitation validation failed (${response.status})`));
  }

  return (await response.json()) as ValidateInvitationResponse;
}

export async function refreshWithToken(refresh_token?: string): Promise<TokenResponse> {
  const response = await fetch(`${PLATFORM_API_BASE_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Portal-Context": "user",
    },
    body: JSON.stringify(refresh_token ? { refresh_token } : {}),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Session refresh failed (${response.status})`));
  }

  return (await response.json()) as TokenResponse;
}

export async function logoutSession(): Promise<void> {
  const response = await fetch(`${PLATFORM_API_BASE_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers: {
      "X-Portal-Context": "user",
    },
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Logout failed (${response.status})`));
  }
}
