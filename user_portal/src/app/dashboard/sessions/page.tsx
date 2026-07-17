import { redirect } from "next/navigation";

export default function LegacySessionsRedirectPage() {
  redirect("/dashboard/security?tab=security");
}
