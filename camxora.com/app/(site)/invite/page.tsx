import type { Metadata } from "next";
import { InviteView } from "@/components/InviteView";

export const metadata: Metadata = {
  title: "Invite friends",
};

export default function InvitePage() {
  return <InviteView />;
}
