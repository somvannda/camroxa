import type { Metadata } from "next";
import { CreatorStudioView } from "@/components/CreatorStudioView";

export const metadata: Metadata = {
  title: "Creator Studio",
  description: "Claim your Camxora creator page, edit your profile, and track your progress.",
};

export default function CreatorStudioPage() {
  return <CreatorStudioView />;
}
