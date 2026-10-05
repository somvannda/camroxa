import Link from "next/link";

export default function AdminNotFound() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <p className="text-sm text-[var(--muted)]">That admin section doesn&apos;t exist.</p>
      <Link
        href="/admin"
        className="inline-block rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--muted)] hover:bg-white/5"
      >
        Back to dashboard
      </Link>
    </div>
  );
}
