import type { Metadata } from "next";
import { ChartsView } from "@/components/ChartsView";

export const metadata: Metadata = {
  title: "Charts",
};

export default function ChartsPage() {
  return <ChartsView />;
}
