import type { Metadata } from "next";
import { CreatorPayoutsView } from "@/components/CreatorPayoutsView";

export const metadata: Metadata = {
  title: "Creator Payouts",
  description: "Complete payout verification and request payouts from your creator balance.",
};

export default function CreatorPayoutsPage() {
  return <CreatorPayoutsView />;
}
