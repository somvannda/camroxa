import Link from "next/link";
import { ArrowRight, CheckCircle2, LayoutDashboard } from "lucide-react";

import { PortalMarketingShell } from "@/components/auth/portal-marketing-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { getWebsiteBaseUrl } from "@/lib/site-urls";

export default function OnboardingDonePage() {
  const websiteBaseUrl = getWebsiteBaseUrl();

  return (
    <PortalMarketingShell active="login" wide>
      <div className="relative flex min-h-[68vh] w-full items-center justify-center overflow-hidden px-2 py-12 md:px-6 xl:justify-end">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(900px_circle_at_30%_20%,hsl(var(--primary)/0.18),transparent_55%),radial-gradient(700px_circle_at_70%_80%,hsl(217_90%_68%/0.12),transparent_60%)]" />
          <div className="absolute inset-0 bg-[linear-gradient(to_bottom,hsl(var(--background)),hsl(var(--background)/0.92))]" />
        </div>

        <Card className="relative w-full max-w-xl border-border/70 bg-card/85 shadow-[0_24px_70px_rgba(18,24,58,0.42)] backdrop-blur supports-[backdrop-filter]:bg-card/70 xl:mr-12">
          <CardHeader className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="font-display text-2xl font-semibold tracking-tight">
                  Onboarding complete
                </div>
                <div className="text-sm text-muted-foreground">
                  Your workspace is ready. Continue in the user panel or sign in on the desktop app.
                </div>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-md border border-emerald-400/30 bg-emerald-400/10">
                <CheckCircle2 className="h-5 w-5 text-emerald-300" />
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="text-sm text-muted-foreground">
              If you reached this page directly, use the dashboard to review your channel setup and continue into the wider CAMXORA product flow.
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <Button asChild className="w-full sm:w-auto">
                <Link href="/dashboard">
                  Open dashboard
                  <LayoutDashboard className="h-4 w-4" />
                </Link>
              </Button>
              <Button variant="outline" asChild className="w-full sm:w-auto">
                <Link href={`${websiteBaseUrl}/download`}>
                  Download app
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </PortalMarketingShell>
  );
}
