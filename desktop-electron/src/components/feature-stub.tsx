import { Icon } from "./icon";
import { Badge } from "./status";
import { Card } from "./card";
import { PageHeader } from "./page-header";

export function FeatureStub({
  title,
  description,
  phase,
  items,
}: {
  title: string;
  description: string;
  phase: string;
  items: string[];
}) {
  return (
    <div>
      <PageHeader
        eyebrow="Workspace"
        title={title}
        description={description}
        actions={<Badge tone="neutral">{phase}</Badge>}
      />
      <div className="p-6">
        <Card className="max-w-2xl p-5">
          <div className="flex items-start gap-3">
            <Icon name="fa-circle-notch" size={18} className="mt-0.5 text-text-muted" />
            <div>
              <h2 className="text-title font-semibold text-text-primary">
                {title} is planned for {phase}
              </h2>
              <p className="mt-1 text-body text-text-secondary">
                The route and shell are ready. The page implementation follows its requirements
                document and acceptance checklist.
              </p>
              <ul className="mt-3 space-y-1 text-body text-text-secondary">
                {items.map((item) => (
                  <li key={item}>• {item}</li>
                ))}
              </ul>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
