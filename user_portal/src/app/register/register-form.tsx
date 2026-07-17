"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Lock, Mail, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { saveSession } from "@/lib/auth";
import {
  getSignupMode,
  loginWithEmailPassword,
  registerWithEmailPassword,
  validateInvitationCode,
} from "@/lib/platform-api";
import { useSearchParams } from "next/navigation";

export function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [displayName, setDisplayName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [invitationCode, setInvitationCode] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [isAccessResolved, setIsAccessResolved] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        const mode = await getSignupMode();
        if (cancelled) return;

        if (mode.mode !== "invite_only") {
          setIsAccessResolved(true);
          return;
        }

        const invite = searchParams.get("invite")?.trim() ?? "";
        if (!invite) {
          router.replace("/invite");
          return;
        }

        await validateInvitationCode(invite);
        if (cancelled) return;
        setInvitationCode(invite.toUpperCase());
        setIsAccessResolved(true);
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : "Unable to verify signup access";
        toast({ variant: "destructive", title: "Signup unavailable", description: message });
        router.replace("/invite");
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [router, searchParams]);

  const canSubmit =
    isAccessResolved &&
    displayName.trim().length >= 2 &&
    email.trim().length > 0 &&
    password.trim().length >= 8 &&
    !isSubmitting;

  if (!isAccessResolved) {
    return (
      <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] shadow-[0_24px_80px_rgba(33,16,64,0.2)] ring-1 ring-white/6 backdrop-blur supports-[backdrop-filter]:bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))]">
        <CardHeader className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="font-display text-2xl font-semibold tracking-tight text-white">
                Create account
              </div>
              <div className="text-sm leading-6 text-slate-200/70">
                Verifying signup access before showing the registration form.
              </div>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04]">
              <UserRound className="h-4 w-4 animate-pulse text-fuchsia-100" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-5 text-sm text-slate-300">
            Checking invitation or open-signup availability...
          </div>
        </CardContent>
      </Card>
    );
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;

    setIsSubmitting(true);
    try {
      await registerWithEmailPassword({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        ...(invitationCode ? { invitation_code: invitationCode } : {}),
      });

      const tokens = await loginWithEmailPassword({
        email: email.trim(),
        password,
      });
      saveSession(tokens);

      toast({
        title: "Account created",
        description: "Confirm your email to continue onboarding.",
      });
      router.push("/onboarding");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Registration failed";
      toast({ variant: "destructive", title: "Create account failed", description: message });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card className="rounded-[28px] border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] shadow-[0_24px_80px_rgba(33,16,64,0.2)] ring-1 ring-white/6 backdrop-blur supports-[backdrop-filter]:bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))]">
      <CardHeader className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-display text-2xl font-semibold tracking-tight text-white">
              Create account
            </div>
            <div className="text-sm leading-6 text-slate-200/70">
              Start with your account, then continue into confirmation and channel setup.
            </div>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04]">
            <UserRound className="h-4 w-4 text-fuchsia-100" />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form className="grid gap-4" onSubmit={onSubmit}>
          {invitationCode ? (
            <div className="grid gap-2">
              <Label className="text-slate-100" htmlFor="invitation_code">Invitation code</Label>
              <Input
                id="invitation_code"
                type="text"
                value={invitationCode}
                readOnly
                className="border-white/10 bg-white/[0.04] font-mono text-xs text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
              />
              <div className="text-xs leading-5 text-slate-400">
                This signup is invitation-only. If you need a different code, open the invite link again.
              </div>
            </div>
          ) : null}
          <div className="grid gap-2">
            <Label className="text-slate-100" htmlFor="display_name">Display name</Label>
            <div className="relative">
              <UserRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="display_name"
                type="text"
                placeholder="Your name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="border-white/10 bg-white/[0.04] pl-10 text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
                autoComplete="name"
                required
              />
            </div>
          </div>

          <div className="grid gap-2">
            <Label className="text-slate-100" htmlFor="email">Email</Label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="email"
                type="email"
                placeholder="you@camxora.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="border-white/10 bg-white/[0.04] pl-10 text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
                autoComplete="email"
                required
              />
            </div>
          </div>

          <div className="grid gap-2">
            <Label className="text-slate-100" htmlFor="password">Password</Label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="password"
                type="password"
                placeholder="8+ chars, uppercase, lowercase, number"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="border-white/10 bg-white/[0.04] pl-10 text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
                autoComplete="new-password"
                required
              />
            </div>
          </div>

          <Button
            type="submit"
            disabled={!canSubmit}
            className="w-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-[0_18px_44px_rgba(118,77,255,0.28)] hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
          >
            {isSubmitting ? "Creating account..." : "Create account"}
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>
      </CardContent>
      <CardFooter className="flex items-center justify-between gap-3">
        <div className="text-sm text-slate-300/72">
          Already have an account?{" "}
          <Link className="text-white underline-offset-4 hover:underline" href="/login">
            Sign in
          </Link>
        </div>
        <Link className="text-sm text-slate-300/72 underline-offset-4 hover:text-white hover:underline" href="/login">
          Sign in
        </Link>
      </CardFooter>
    </Card>
  );
}
