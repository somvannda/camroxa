import Sidebar from "@/components/Sidebar";

// Access control lives in proxy.ts (server-side, via the API's /auth/me),
// so this layout only handles chrome.
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-8">{children}</main>
    </div>
  );
}
