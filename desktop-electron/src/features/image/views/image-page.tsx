import { FeatureStub } from "../../../components/feature-stub";

export function ImagePage() {
  return (
    <FeatureStub
      title="Image"
      description="Image job queue, previews and prompt settings."
      phase="P5"
      items={[
        "Date filters, stat tiles and the grouped job queue",
        "Background/thumbnail previews and file actions",
        "Prompt autosave, retry and clear queue",
      ]}
    />
  );
}
