import { redirect } from "next/navigation";

export default async function LegacyCreditsRedirectPage({
  searchParams,
}: {
  searchParams: Promise<{
    payment_id?: string;
    status?: string;
    reference_id?: string;
  }>;
}) {
  const params = await searchParams;
  const query = new URLSearchParams({ tab: "credits" });
  if (params.payment_id) query.set("payment_id", params.payment_id);
  if (params.status) query.set("status", params.status);
  if (params.reference_id) query.set("reference_id", params.reference_id);
  redirect(`/dashboard/billing?${query.toString()}`);
}
