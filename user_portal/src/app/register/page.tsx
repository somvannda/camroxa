import { RegisterForm } from "@/app/register/register-form";
import { PortalMarketingShell } from "@/components/auth/portal-marketing-shell";
import { Suspense } from "react";

export default function RegisterPage() {
  return (
    <PortalMarketingShell active="register" compact>
      <Suspense fallback={null}>
        <RegisterForm />
      </Suspense>
    </PortalMarketingShell>
  );
}
