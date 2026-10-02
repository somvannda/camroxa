"use client";

import { AuthModalProvider } from "@/lib/auth-modal";

export default function ClientProviders({ children }: { children: React.ReactNode }) {
  return <AuthModalProvider>{children}</AuthModalProvider>;
}
