export default function ComingSoon({ title }: { title: string }) {
  return (
    <div>
      <h1 className="text-2xl font-bold">{title}</h1>
      <div className="glass mt-6 rounded-2xl p-8 text-sm text-[var(--muted)]">
        This section is under construction.
      </div>
    </div>
  );
}
