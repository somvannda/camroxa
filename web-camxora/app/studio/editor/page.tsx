import type { Metadata } from "next";
import { StudioEditorView } from "@/components/StudioEditorView";

export const metadata: Metadata = {
  title: "Studio Editor",
};

export default function StudioEditorPage() {
  return <StudioEditorView />;
}
