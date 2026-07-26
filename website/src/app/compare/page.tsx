import { redirect } from "next/navigation";

/** Compare pitch now lives on the homepage. Keep this route for old links. */
export default function ComparePage() {
  redirect("/");
}
