import { FeatureStub } from "../../../components/feature-stub";

export function MusicPage() {
  return (
    <FeatureStub
      title="Music"
      description="Batch composer, song editor, automation and history."
      phase="P4"
      items={[
        "Settings strip: dates, language, creativity, strictness, count",
        "Song editor: draft/polish, effects, copies, lyrics",
        "Channel pairs, automation card, credit plan and Generate",
        "History table and background downloads",
      ]}
    />
  );
}
