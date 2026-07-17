import { redirect } from "next/navigation";

import { PortalMarketingShell } from "@/components/auth/portal-marketing-shell";
import { InviteForm } from "@/app/invite/invite-form";

export const dynamic = "force-dynamic";

async function fetchSignupMode(): Promise<"open" | "invite_only" | null> {
  const apiBase =
    process.env.PLATFORM_API_INTERNAL_URL?.trim() ||
    process.env.NEXT_PUBLIC_PLATFORM_API_BASE_URL?.trim() ||
    (process.env.NODE_ENV === "production" ? "http://127.0.0.1:8100/api/v1" : "http://localhost:8000/api/v1");

  try {
    const response = await fetch(`${apiBase.replace(/\/$/, "")}/auth/signup-mode`, {
      headers: { "X-Portal-Context": "user" },
      cache: "no-store",
    });
    if (!response.ok) return null;
    const data = (await response.json()) as { mode?: string };
    if (data.mode === "open") return "open";
    if (data.mode === "invite_only") return "invite_only";
    return null;
  } catch {
    return null;
  }
}

export default async function InvitePage() {
  const mode = await fetchSignupMode();
  if (mode === "open") {
    redirect("/register");
  }

  return (
    <PortalMarketingShell active="register" compact>
      <InviteForm />
    </PortalMarketingShell>
  );
}
