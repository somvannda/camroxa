import { redirect } from "next/navigation";

// proxy.ts already guarantees an active admin session for "/", so just
// land them on the console.
export default function Home() {
  redirect("/admin");
}
