export default function AdminLoading() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading">
      <div className="h-8 w-48 animate-pulse rounded-lg bg-white/5" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="glass h-24 animate-pulse rounded-xl" />
        ))}
      </div>
      <div className="glass h-64 animate-pulse rounded-xl" />
    </div>
  );
}
