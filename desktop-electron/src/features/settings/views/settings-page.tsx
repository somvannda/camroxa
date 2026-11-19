import { FeatureStub } from "../../../components/feature-stub";

export function SettingsPage() {
  return (
    <FeatureStub
      title="Settings"
      description="Manage channel profiles, publication, preferences, prompts, pools and Suno."
      phase="P2/P8"
      items={[
        "Profiles: list, editor, logo/cover, templates, save/delete",
        "Publication: visibility, schedule, category, playlist, templates",
        "Preferences: paths, workers, image rendering, storage, diagnostics",
      ]}
    />
  );
}
