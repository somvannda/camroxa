import { Icon } from "../../components/icon";
import type { ShellRoute } from "../../shell/routes";
import { Card } from "../../components/card";
import { PageHeader } from "../../components/page-header";
import { Badge } from "../../components/status";

export function PlaceholderPage({ route }: { route: ShellRoute }) {
  return (
    <div>
      <PageHeader
        eyebrow="Workspace"
        title={route.label}
        description={route.description}
        actions={<Badge tone="neutral">{route.phase}</Badge>}
      />
      <div className="p-6">
        <Card className="max-w-2xl p-5">
          <div className="flex items-start gap-3">
            <Icon name="fa-circle-notch" size={18} className="mt-0.5 text-text-muted" />
            <div>
              <h2 className="text-title font-semibold text-text-primary">
                {route.label} is planned for {route.phase}
              </h2>
              <p className="mt-1 text-body text-text-secondary">
                This route is registered in the shell so navigation, layout and telemetry are
                already in place. The page implementation follows its requirements document and
                acceptance checklist.
              </p>
              <p className="mt-3 text-meta text-text-muted">
                Checklist: docs/electron-desktop/pages
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
