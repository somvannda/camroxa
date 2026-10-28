import type { Metadata } from "next";
import { ArtistDashboardView } from "@/components/ArtistDashboardView";

export const metadata: Metadata = {
  title: "Creator dashboard",
};

export default function ArtistDashboardPage() {
  return <ArtistDashboardView />;
}
