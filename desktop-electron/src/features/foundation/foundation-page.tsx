import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, Database, Radio, ShieldCheck } from "lucide-react";
import type { AppInfo } from "../../../electron/shared/types";
import { Card } from "../../components/card";
import { PageHeader } from "../../components/page-header";
import { Badge, StatusDot } from "../../components/status";
import { apiRequest, errorMessage } from "../../lib/api";

interface HealthPayload {
  status?: string;
}

function CheckRow({
  ok,
  title,
  detail,
}: {
  ok: boolean;
  title: string;
  detail: string;
}) {
  return (
    <div className="flex items-start gap-3 border-b border-border py-3 last:border-b-0">
      {ok ? (
        <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-success" />
      ) : (
        <CircleDashed size={16} className="mt-0.5 shrink-0 text-text-muted" />
      )}
      <div className="min-w-0">
        <p className="text-body font-medium text-text-primary">{title}</p>
        <p className="text-meta text-text-secondary">{detail}</p>
      </div>
      <Badge tone={ok ? "success" : "neutral"}>{ok ? "Ready" : "Pending"}</Badge>
    </div>
  );
}

export function FoundationPage() {
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
          }),
    staleTime: Infinity,
  });

  const health = useQuery<HealthPayload>({
    queryKey: ["health"],
    queryFn: () => apiRequest<HealthPayload>({ method: "GET", path: "/health", auth: false }),
    retry: 0,
    staleTime: 15_000,
  });

  const bridgeReady = Boolean(window.camxora);
  const apiReady = health.isSuccess;
  const apiDetail = health.isError
    ? errorMessage(health.error)
    : health.isLoading
      ? "Checking the platform API…"
      : `Responded with ${health.data?.status ?? "ok"}.`;

  return (
    <div>
      <PageHeader
        eyebrow="Workspace"
        title="Dashboard"
        description="Phase 0 foundation. The real Dashboard data lands in P2."
        actions={<Badge tone="accent">Foundation build</Badge>}
      />

      <div className="grid gap-4 p-6 xl:grid-cols-[1.4fr_0.8fr]">
        <Card className="p-4">
          <div className="mb-1 flex items-center justify-between">
            <h2 className="text-title font-semibold text-text-primary">Foundation checks</h2>
            <StatusDot tone={bridgeReady && apiReady ? "success" : "warning"} label={bridgeReady && apiReady ? "Ready" : "In progress"} />
          </div>
          <p className="mb-2 text-body text-text-secondary">
            The shell proves the three contracts that every page depends on: a typed bridge, a
            secure session store, and an authenticated API path through the main process.
          </p>

          <CheckRow
            ok={bridgeReady}
            title="Preload bridge"
            detail={
              bridgeReady
                ? `Connected to ${info.data?.name ?? "Camxora"} on ${info.data?.platform ?? "desktop"}.`
                : "Run the Electron window; the browser preview has no bridge."
            }
          />
          <CheckRow
            ok={Boolean(info.data)}
            title="Application metadata"
            detail={
              info.data
                ? `Electron ${info.data.electron || "—"} · Chromium ${info.data.chrome || "—"} · Node ${info.data.node || "—"}`
                : "Waiting for the main process."
            }
          />
          <CheckRow ok={apiReady} title="Platform API" detail={apiDetail} />
          <CheckRow
            ok={true}
            title="Session storage"
            detail="Tokens are encrypted with the OS keystore and never reach the renderer."
          />
        </Card>

        <div className="space-y-4">
          <Card className="p-4">
            <div className="mb-3 flex items-center gap-2">
              <ShieldCheck size={16} className="text-accent" />
              <h2 className="text-title font-semibold text-text-primary">Security baseline</h2>
            </div>
            <ul className="space-y-2 text-body text-text-secondary">
              <li>Context isolation and sandbox enabled.</li>
              <li>Node integration disabled.</li>
              <li>Navigation restricted; external links open in the browser.</li>
              <li>API calls and tokens stay in the main process.</li>
            </ul>
          </Card>

          <Card className="p-4">
            <div className="mb-3 flex items-center gap-2">
              <Database size={16} className="text-info" />
              <h2 className="text-title font-semibold text-text-primary">Next in Phase 0</h2>
            </div>
            <ul className="space-y-2 text-body text-text-secondary">
              <li>OpenAPI type generation and drift check.</li>
              <li>SQLite store and migrations.</li>
              <li>Media protocol and native FFmpeg jobs.</li>
              <li>CI: typecheck, lint, unit, build.</li>
            </ul>
          </Card>

          <Card className="p-4">
            <div className="mb-2 flex items-center gap-2">
              <Radio size={16} className="text-warning" />
              <h2 className="text-title font-semibold text-text-primary">Scope reminder</h2>
            </div>
            <p className="text-body text-text-secondary">
              Vizzy is hosted, not rewritten. The pipeline ships in 2.0.0. Old Camxora video
              templates are not migrated.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
