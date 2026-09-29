"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight } from "lucide-react";

import { getQuotaRenewal, type QuotaRenewal } from "@/lib/billing";

const REMIND_WITHIN_DAYS = 7;

/**
 * In-app renewal reminder: a banner inside the user portal shown when the plan is
 * within a week of expiry (or already expired). No email/Telegram.
 */
export function RenewalReminderBanner() {
  const [renewal, setRenewal] = React.useState<QuotaRenewal | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    getQuotaRenewal()
      .then((result) => {
        if (!cancelled) setRenewal(result);
      })
      .catch(() => {
        if (!cancelled) setRenewal(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!renewal?.eligible) {
    return null;
  }

  const days = renewal.days_left ?? null;
  const expired = renewal.expired === true;
  const due = expired || (days !== null && days <= REMIND_WITHIN_DAYS);
  if (!due) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-400/30 bg-amber-500/[0.10] px-5 py-4">
      <div className="flex items-center gap-3 text-sm text-amber-100">
        <AlertTriangle className="h-5 w-5 shrink-0" />
        <span>
          {expired
            ? "Your plan has expired — renew to keep your studio and credits active."
            : `Your plan expires in ${days} day${days === 1 ? "" : "s"} — renew now to avoid interruption.`}
        </span>
      </div>
      <Link
        href="/dashboard/billing"
        className="inline-flex h-9 items-center gap-1 rounded-xl bg-gradient-to-r from-[#7466F1] to-[#A259FF] px-4 text-sm font-medium text-white"
      >
        Renew now
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
