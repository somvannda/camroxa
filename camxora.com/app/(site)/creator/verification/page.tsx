import type { Metadata } from "next";
import { CreatorVerificationView } from "@/components/CreatorVerificationView";

export const metadata: Metadata = {
  title: "Creator Verification",
  description: "Apply for Verified Creator status and track your review.",
};

export default function CreatorVerificationPage() {
  return <CreatorVerificationView />;
}
