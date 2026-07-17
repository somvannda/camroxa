"use client";

import * as React from "react";
import { ArrowRight, KeyRound } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { getSignupMode, validateInvitationCode } from "@/lib/platform-api";

export function InviteForm() {
  const router = useRouter();
  const [code, setCode] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        const mode = await getSignupMode();
        if (cancelled) return;
        if (mode.mode === "open") {
          router.replace("/register");
        }
      } catch {
        if (!cancelled) return;
      }
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const normalizedCode = code.trim().toUpperCase();
  const canSubmit = normalizedCode.length >= 6 && !isSubmitting;

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setIsSubmitting(true);
    try {
      await validateInvitationCode(normalizedCode);
      router.push(`/register?invite=${encodeURIComponent(normalizedCode)}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Invalid invitation code";
      toast({ variant: "destructive", title: "Invalid invitation code", description: message });
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
              Invitation required
            </div>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04]">
            <KeyRound className="h-4 w-4 text-fuchsia-100" />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form className="grid gap-4" onSubmit={onSubmit}>
          <div className="grid gap-2">
            <Label className="text-slate-100" htmlFor="invite_code">Invitation code</Label>
            <Input
              id="invite_code"
              type="text"
              placeholder="e.g. A1B2C3D4E5F6"
              value={normalizedCode}
              onChange={(e) => setCode(e.target.value)}
              className="border-white/10 bg-white/[0.04] font-mono text-xs text-white placeholder:text-slate-400 focus-visible:ring-fuchsia-400/60"
              autoComplete="off"
              required
            />
          </div>
          <Button
            type="submit"
            disabled={!canSubmit}
            className="w-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 text-white shadow-[0_18px_44px_rgba(118,77,255,0.28)] hover:from-violet-400 hover:via-purple-400 hover:to-fuchsia-400"
          >
            {isSubmitting ? "Validating..." : "Continue to signup"}
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
