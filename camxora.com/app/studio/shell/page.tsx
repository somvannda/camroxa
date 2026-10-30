import type { Metadata } from "next";
import { Suspense } from "react";

import { StudioEditorShell } from "@/components/studio/StudioEditorShell";

export const metadata: Metadata = {
  title: "Studio",
};

export default function StudioShellPage() {
  return (
    <Suspense fallback={null}>
      <StudioEditorShell />
    </Suspense>
  );
}
