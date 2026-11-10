import type { Metadata } from "next";
import { CreatorEarningsView } from "@/components/CreatorEarningsView";

export const metadata: Metadata = {
  title: "Creator Earnings",
  description: "Track which songs are eligible to earn and what is left to unlock.",
};

export default function CreatorEarningsPage() {
  return <CreatorEarningsView />;
}
