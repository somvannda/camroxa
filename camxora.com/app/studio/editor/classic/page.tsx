import type { Metadata } from "next";
import { Suspense } from "react";

import { StudioEditorView } from "@/components/StudioEditorView";

export const metadata: Metadata = {
  title: "Studio Editor (classic)",
};

/** Previous editor, kept reachable while the reference-layout shell takes over. */
export default function StudioEditorClassicPage() {
  return (
    <Suspense fallback={null}>
      <StudioEditorView />
    </Suspense>
  );
}
