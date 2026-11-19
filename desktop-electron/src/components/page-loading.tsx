export function PageLoading() {
  return (
    <div className="flex h-full min-h-[320px] items-center justify-center p-6">
      <div className="flex items-center gap-3 text-body text-text-muted">
        <span className="h-4 w-4 animate-spin rounded-full border border-accent border-t-transparent" />
        Loading workspace
      </div>
    </div>
  );
}
