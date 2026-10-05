"use client";

/**
 * Route-level error boundary for the admin console. Catches render/data
 * failures in any `/admin/*` page so a single broken page can't white-screen
 * the whole shell.
 */
export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Something went wrong</h1>
        <p className="text-sm text-[var(--muted)]">The page failed to load.</p>
      </div>
      <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
        {error.message || "An unexpected error occurred."}
      </p>
      <button
        onClick={reset}
        className="grad-bg rounded-lg px-4 py-2 text-sm font-semibold text-white"
      >
        Try again
      </button>
    </div>
  );
}
