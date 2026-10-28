import type { Metadata } from "next";
import { RedeemView } from "@/components/RedeemView";

export const metadata: Metadata = {
  title: "Redeem code",
};

export default function RedeemPage() {
  return <RedeemView />;
}
