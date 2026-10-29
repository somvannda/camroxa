import type { Metadata } from "next";
import { Suspense } from "react";
import { StudioShell } from "@/components/StudioShell";

export const metadata: Metadata = {
  title: "Studio",
};

export default function StudioEditorPage() {
  return (
    <Suspense fallback={null}>
      <StudioShell />
    </Suspense>
  );
}
