import type { Metadata } from "next";
import { Suspense } from "react";

import { StudioEditorShell } from "@/components/studio/StudioEditorShell";

export const metadata: Metadata = {
  title: "Studio",
};

/**
 * The editor is the reference-layout shell. The previous editor remains at
 * `/studio/editor/classic` and is linked from the shell footer.
 */
export default function StudioEditorPage() {
  return (
    <Suspense fallback={null}>
      <StudioEditorShell />
    </Suspense>
  );
}
