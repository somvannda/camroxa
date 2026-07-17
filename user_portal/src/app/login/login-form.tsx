"use client"

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Lock, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { saveSession } from "@/lib/auth";
import { getProfilesStatus } from "@/lib/channel-setup";
import { loginWithEmailPassword } from "@/lib/platform-api";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const canSubmit = email.trim().length > 0 && password.trim().length >= 8 && !isSubmitting;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    setIsSubmitting(true);
    try {
      const tokens = await loginWithEmailPassword({
        email: email.trim(),
        password,
      });

      saveSession(tokens);
      const status = await getProfilesStatus();
      if (status.profile_count > 0) {
        toast({
          title: "Signed in",
          description:
            status.profile_count >= 2
              ? "Your onboarding is already complete."
              : "Continue onboarding to finish the remaining profile setup.",
        });
        router.push(status.profile_count >= 2 ? "/dashboard" : "/onboarding");
        return;
      }

      toast({ title: "Signed in", description: "Continue to onboarding." });
      router.push("/onboarding");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed";
      toast({ variant: "destructive", title: "Sign in failed", description: message });
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
              Sign in
            </div>
            <div className="text-sm leading-6 text-slate-200/70">
              Use your CAMXORA account to continue into onboarding or desktop production.
            </div>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04]">
            <Lock className="h-4 w-4 text-fuchsia-100" />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form className="grid gap-4" onSubmit={onSubmit}>
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
                placeholder="Minimum 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="border-white/10 bg-white/[0.04] pl-10 text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
                autoComplete="current-password"
                required
              />
            </div>
          </div>

          <Button
            type="submit"
            disabled={!canSubmit}
            className="w-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-[0_18px_44px_rgba(118,77,255,0.28)] hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
          >
            {isSubmitting ? "Signing in..." : "Sign in"}
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>
      </CardContent>
      <CardFooter className="flex items-center justify-between gap-3">
        <div className="text-sm text-slate-300/72">
          New here?{" "}
          <Link className="text-white underline-offset-4 hover:underline" href="/register">
            Create an account
          </Link>
        </div>
        <Link className="text-sm text-slate-300/72 underline-offset-4 hover:text-white hover:underline" href="/register">
          Sign up
        </Link>
      </CardFooter>
    </Card>
  );
}
