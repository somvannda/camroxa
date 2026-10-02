"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import GoogleSignInButton from "@/components/google-signin-button";

interface Props {
  open: boolean;
  mode: "login" | "signup";
  onClose: () => void;
  onModeChange: (m: "login" | "signup") => void;
}

export default function AuthModal({ open, onClose }: Props) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const dialogRef = useRef<HTMLDialogElement | null>(null);

  useEffect(() => {
    const d = dialogRef.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
    } else if (!open && d.open) {
      d.close();
    }
  }, [open]);

  useEffect(() => {
    if (open) {
      setError("");
      setLoading(false);
    }
  }, [open]);

  const handleCancel = useCallback(() => {
    onClose();
  }, [onClose]);

  return (
    <dialog
      ref={dialogRef}
      onCancel={handleCancel}
      className="backdrop:bg-black/70 open:flex open:items-center open:justify-center open:z-50 rounded-2xl border border-white/10 bg-transparent p-0 backdrop-blur-sm"
    >
      <div
        onClick={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
        className="-m-8 flex min-h-[70vh] min-w-[90vw] items-center justify-center p-8 sm:min-w-0 sm:min-h-0 sm:-m-12 sm:p-12"
      >
        <div onClick={(e) => e.stopPropagation()} className="glass w-full max-w-md rounded-2xl p-8 space-y-6 relative">
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="absolute right-3 top-3 inline-flex h-8 w-8 items-center justify-center rounded-lg text-[var(--muted)] hover:bg-white/10 hover:text-white"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>

          <div className="text-center">
            <div className="grad-bg mx-auto mb-4 h-11 w-11 rounded-xl" />
            <h2 className="text-2xl font-bold">Sign in</h2>
            <p className="text-sm text-[var(--muted)]">Camxora Music API workspace</p>
          </div>

          <GoogleSignInButton
            label="Continue with Google"
            redirectTo="/dashboard"
            onSuccess={() => {
              onClose();
              router.replace("/dashboard");
            }}
          />

          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}

          <p className="text-center text-xs text-[var(--muted)]">
            By continuing, you agree to our{" "}
            <Link href="/terms" className="underline hover:text-white">
              Terms
            </Link>{" "}
            and acknowledge our{" "}
            <Link href="/privacy" className="underline hover:text-white">
              Privacy Policy
            </Link>
            .
          </p>
        </div>
      </div>
    </dialog>
  );
}
