import { PortalMarketingShell } from "@/components/auth/portal-marketing-shell";
import { LoginForm } from "@/app/login/login-form";

export default function LoginPage() {
  return (
    <PortalMarketingShell active="login" compact>
      <LoginForm />
    </PortalMarketingShell>
  );
}
