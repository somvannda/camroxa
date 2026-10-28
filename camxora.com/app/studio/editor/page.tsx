import type { Metadata } from "next";
import { Suspense } from "react";
import { StudioEditorView } from "@/components/StudioEditorView";

export const metadata: Metadata = {
  title: "Studio Editor",
};

export default function StudioEditorPage() {
  return (
    <Suspense fallback={null}>
      <StudioEditorView />
    </Suspense>
  );
}
