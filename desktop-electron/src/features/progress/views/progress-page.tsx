import { FeatureStub } from "../../../components/feature-stub";

export function ProgressPage() {
  return (
    <FeatureStub
      title="Progress"
      description="Live run stages, recovery actions and pending downloads."
      phase="P3"
      items={[
        "Filters, stat cards and the operational table",
        "Runtime overlay for converter/merge/reel stages",
        "Manual asset recovery and the download queue",
      ]}
    />
  );
}
