import { redirect } from "next/navigation";

export default function LegacyNotificationsRedirectPage() {
  redirect("/dashboard/account?tab=notifications");
}
