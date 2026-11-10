import type { Metadata } from "next";
import { CreatorDirectoryView } from "@/components/CreatorDirectoryView";

export const metadata: Metadata = {
  title: "Creators",
  description: "Discover verified and emerging creators building Khmer music on Camxora.",
};

export default function CreatorsPage() {
  return <CreatorDirectoryView />;
}
