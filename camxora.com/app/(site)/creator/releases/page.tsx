import type { Metadata } from "next";
import { CreatorReleasesView } from "@/components/CreatorReleasesView";

export const metadata: Metadata = {
  title: "Creator Releases",
  description: "Move a finished generation from draft to live on Camxora.",
};

export default function CreatorReleasesPage() {
  return <CreatorReleasesView />;
}
