import { useQuery } from "@tanstack/react-query";
import { StatusDot } from "../components/status";
import type { AppInfo } from "../../electron/shared/types";

export function Footer() {
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

  return (
    <footer className="flex h-7 shrink-0 items-center justify-between border-t border-border bg-sidebar px-4 text-caption text-text-muted">
      <div className="flex items-center gap-4">
        <StatusDot tone="success" label="Ready" />
        <span>2.0.0 preview</span>
      </div>
      <div className="flex items-center gap-4 font-mono text-tabular">
        <span>{info.data?.env ?? "development"}</span>
        <span>v{info.data?.version ?? "2.0.0"}</span>
        <span>{info.data?.platform ?? "desktop"}</span>
      </div>
    </footer>
  );
}
