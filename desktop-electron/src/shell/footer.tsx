import { useQuery } from "@tanstack/react-query";
import { Badge, StatusDot } from "../components/status";
import type { AppInfo } from "../../electron/shared/types";
import { apiRequest } from "../lib/api";
import { formatCredits } from "../lib/format";
import type { ChannelProfile, UserMe } from "../features/dashboard/account-types";
import { useSessionStore } from "../store/session";

interface FooterSummary {
  credits: number | null;
  profiles: number | null;
  profileCap: number | null;
}

/**
 * Bottom bar shared by the shell and the auth screens, matching the legacy
 * desktop footer: status on the left, API environment and version on the right,
 * plus credits and profile allowance once signed in.
 */
export function Footer({ variant = "app" }: { variant?: "app" | "auth" }) {
  const session = useSessionStore((state) => state.session);
  const info = useQuery<AppInfo>({
    queryKey: ["app-info"],
    queryFn: () =>
      window.camxora
        ? window.camxora.app.info()
        : Promise.resolve({
            name: "Camxora",
            version: "2.0.0",
            env: "browser-preview",
            platform: "web",
            electron: "",
            chrome: "",
            node: "",
            devBypass: true,
            portalUrl: "https://app.camxora.com",
            build: "browser",
            apiBaseUrl: "",
          }),
    staleTime: Infinity,
  });

  const summary = useQuery<FooterSummary>({
    queryKey: ["footer-summary"],
    enabled: variant === "app" && Boolean(session) && Boolean(window.camxora),
    queryFn: async () => {
      const [me, profiles] = await Promise.all([
        apiRequest<UserMe>({ method: "GET", path: "/users/me" }),
        apiRequest<ChannelProfile[]>({ method: "GET", path: "/profiles" }).catch(
          () => [] as ChannelProfile[],
        ),
      ]);
      return {
        credits: Number.isFinite(me.credit_balance) ? me.credit_balance : null,
        profiles: Array.isArray(profiles) ? profiles.length : null,
        profileCap: me.effective_profile_allowance ?? me.profile_allowance ?? null,
      };
    },
    staleTime: 30_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const env = info.data?.env ?? "development";
  const apiBase = info.data?.apiBaseUrl ?? "";
  const sandboxApi = /sandbox/i.test(apiBase) || env === "sandbox";
  const productionApi =
    !sandboxApi && (env === "production" || /(^|\.)api\.camxora\.com/i.test(apiBase));
  const envLabel = productionApi
    ? null
    : sandboxApi
      ? "Sandbox API"
      : /localhost|127\.0\.0\.1/i.test(apiBase) || !apiBase
        ? "Local API"
        : "Dev API";

  const credits =
    summary.data?.credits != null ? `${formatCredits(summary.data.credits)} credits` : "-- credits";
  const profiles =
    summary.data?.profiles != null
      ? summary.data.profileCap != null
        ? `${summary.data.profiles} / ${summary.data.profileCap} profiles`
        : `${summary.data.profiles} ${summary.data.profiles === 1 ? "profile" : "profiles"}`
      : "-- profiles";

  return (
    <footer className="flex h-10 shrink-0 items-center justify-between gap-3 border-t border-border bg-sidebar px-4 text-caption text-text-muted">
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {variant === "app" ? <StatusDot tone="success" label="Ready" /> : null}
      </div>

      <div className="flex shrink-0 items-center gap-3 whitespace-nowrap">
        {envLabel ? <Badge tone="neutral">{envLabel}</Badge> : null}
        <span className="font-mono text-tabular" title={`Camxora desktop ${info.data?.version ?? "2.0.0"}`}>
          v{info.data?.version ?? "2.0.0"}
        </span>
        {variant === "app" ? (
          <>
            <span className="h-4 w-px bg-border" />
            <span className="text-tabular">{credits}</span>
            <span className="h-4 w-px bg-border" />
            <span className="text-tabular">{profiles}</span>
          </>
        ) : null}
      </div>
    </footer>
  );
}
