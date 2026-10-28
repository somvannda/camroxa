import type { Metadata } from "next";
import { PricingView } from "@/components/PricingView";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Choose a Camxora plan or top up your music credits.",
};

export default function PricingPage() {
  return <PricingView />;
}
