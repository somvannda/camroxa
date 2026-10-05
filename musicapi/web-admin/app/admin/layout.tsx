import AppShell from "@/components/AppShell";
import { ToastProvider } from "@/components/ui/Toast";

// Access control lives in proxy.ts (server-side, via the API's /auth/me),
// so this layout only handles chrome.
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <AppShell>{children}</AppShell>
    </ToastProvider>
  );
}
