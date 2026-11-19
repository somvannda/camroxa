import { FeatureStub } from "../../../components/feature-stub";

export function MarketplacePage() {
  return (
    <FeatureStub
      title="Marketplace"
      description="Browse, install and manage Vizzy templates."
      phase="P6"
      items={[
        "Catalog filters, search and pagination",
        "Preview cards and installed state",
        "Install/reinstall with template-store validation",
      ]}
    />
  );
}
