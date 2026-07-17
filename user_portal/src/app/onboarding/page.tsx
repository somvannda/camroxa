import { OnboardingWizard } from "@/app/onboarding/wizard";

export default async function OnboardingPage({
  searchParams,
}: {
  searchParams: Promise<{
    payment_id?: string;
    status?: string;
    reference_id?: string;
    mode?: string;
  }>;
}) {
  const params = await searchParams;
  const addonMode = params.mode === "addon";
  return (
    <OnboardingWizard
      returnedPaymentId={params.payment_id ?? null}
      returnedPaymentStatus={params.status ?? null}
      returnedReferenceId={params.reference_id ?? null}
      addonMode={addonMode}
    />
  );
}
