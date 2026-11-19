export function BootSplash() {
  return (
    <div className="flex h-full items-center justify-center bg-bg">
      <div className="flex flex-col items-center gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-accent text-title font-semibold text-accent-ink">
          C
        </div>
        <div className="text-meta font-semibold tracking-[0.16em] text-text-primary">CAMXORA</div>
        <div className="h-0.5 w-32 overflow-hidden rounded-full bg-surface-3">
          <div className="h-full w-1/2 animate-pulse rounded-full bg-accent" />
        </div>
        <p className="text-caption text-text-muted">Preparing your studio</p>
      </div>
    </div>
  );
}
